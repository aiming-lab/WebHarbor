#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Google Search task verification.

Philosophy (same contract as the merriam_webster / phet_simulations / google_map
exemplars): DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     the matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     run the task's search on the mirror (/search?q=... carrying the task's key
     tokens) and, when the answer facts live on the mirror's cached result
     pages, MUST have opened one of those pages; a correct answer with no
     matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / date / number / name containment against ground
     truth hardcoded in each verify_<n>.py (ground truth recorded by browsing
     the served mirror pages with a real Chromium; the catalog is fixed by the
     seeded DB and carries no wall-clock content).
  4. DB integrity check: every task in this file is read-only on the benchmark
     content tables (no login, save, or write is asked for), so an honest run
     leaves the content catalog identical to its seed snapshot. The
     user-generated tables (users, search history, bookmarks, collections,
     feedback, alerts) are excluded: logging in or saving a result is not part
     of any task but would legitimately write those tables. DBs are fetched
     with docker cp from the site container (default $WH_CONTAINER or
     wh-ver-google_search), or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   container to fetch DBs from (default: $WH_CONTAINER or wh-ver-google_search)
  --no_llm           accepted no-op (deterministic-only suite)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote_plus, urlsplit

SITE = "google_search"
TASK_PREFIX = "Google Search--"
DB_FILENAME = "google_search.db"

# Benchmark content tables: define the catalog the ground truth is read from.
# An honest task run never writes any of these through the UI.
CONTENT_TABLES = ("vertical", "google_app", "trending_term", "doodle", "topic",
                  "search_result", "paa_question", "related_query", "knowledge_fact")
# User-generated tables are intentionally NOT compared: signing in, saving a
# bookmark, or creating an alert writes them but no task depends on them.
USER_TABLES = ("user", "search_history", "bookmark", "collection",
               "result_feedback", "alert")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """'Google Search--<n>' inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{TASK_PREFIX}{m.group(1)}" if m else None


def load_run(run_dir):
    """Load and structurally validate the run package. Raises RunPackageError."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run_dir does not exist: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.exists():
        raise RunPackageError(f"missing trajectory.json under {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except Exception as e:
        raise RunPackageError(f"trajectory.json is not valid JSON: {e}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json must contain a JSON object")

    expected = expected_task_id()
    task_id = traj.get("task_id")
    if expected and task_id != expected:
        raise RunPackageError(f"task_id mismatch: expected {expected!r}, got {task_id!r}")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RunPackageError("task_id must be a non-empty string")

    start_url = traj.get("start_url") or ""
    if not re.match(r"^https?://", start_url):
        raise RunPackageError(f"start_url must be an http(s) URL, got {start_url!r}")

    shots_dir = d / "screenshots"
    if not shots_dir.is_dir():
        raise RunPackageError(f"missing screenshots/ directory under {d}")
    shots = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    if not shots:
        raise RunPackageError("no step_*.png screenshots under screenshots/")

    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunPackageError("trajectory must hold a non-empty steps list")

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise RunPackageError(f"step {i} is not an object")
        if not (s.get("url") or s.get("url_after")):
            raise RunPackageError(f"step {i} has no url / url_after")
        for field in ("screenshot_before", "screenshot_after"):
            name = s.get(field)
            if isinstance(name, str) and name:
                if Path(name).name not in shots:
                    raise RunPackageError(
                        f"step {i} references {field} {name!r} which is missing from screenshots/")

    traj["_run_dir"] = d
    traj["_shots"] = shots
    return traj


def load_run_checked(run_dir, judge):
    try:
        return load_run(run_dir)
    except RunPackageError as e:
        judge.check("run_package_valid", False, str(e))
        judge.emit()


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------- navigation
def step_urls(traj):
    """Every recorded step URL (before + after the action) in chronological order."""
    out = []
    for s in traj.get("steps", []):
        for field in ("url", "url_after"):
            u = s.get(field)
            if isinstance(u, str) and u:
                out.append(u)
    return out


def on_site_urls(traj):
    """Step URLs on the mirror origin only. The sandbox blocks the public
    internet, so off-site steps are dead-end navigation attempts and never
    count for nav checks."""
    origin = urlsplit(traj.get("start_url") or "")
    base = f"{origin.scheme}://{origin.netloc}".lower() if origin.netloc else None
    if not base:
        return step_urls(traj)
    return [u for u in step_urls(traj) if u.lower().startswith(base)]


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on on-site step URLs only."""
    needle = substr.lower()
    return sum(1 for u in on_site_urls(traj) if needle in u.lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def _search_queries(traj):
    """Decoded 'q' values of every on-site /search?q=... step URL.
    Only the mirror's own search endpoint counts: the sandbox blocks the
    public internet, so a https://www.google.com/search?q=... step is a
    dead-end navigation attempt, never a task search."""
    out = []
    for u in on_site_urls(traj):
        m = re.search(r"/search\?[^#]*?\bq=([^&#]*)", u)
        if m:
            out.append(unquote_plus(m.group(1)).lower())
    return out


def searched_all_tokens(traj, tokens):
    """True when at least one on-site /search?q=... step carries every token
    (case-insensitive substring, order-free) — the agent ran the task's search."""
    toks = [t.lower() for t in tokens]
    if not toks:
        return False
    return any(all(t in q for t in toks) for q in _search_queries(traj))


def visited_any_page(traj, substrs):
    """True when any on-site, non-search step URL contains one of the
    answer-page markers (an /external/<host>/<path> cached result page, the
    /topic/<slug> page, or a /url?q=... result redirect). Off-site steps are
    ignored entirely and /search?q= pages are excluded: the search query
    itself often contains the same tokens and a SERP is navigation input, not
    an answer page."""
    for u in on_site_urls(traj):
        if "/search?" in u:
            continue
        low = u.lower()
        if any(s.lower() in low for s in substrs):
            return True
    return False


# ---------------------------------------------------------------- answer matching
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def re_any(final, patterns):
    """Case-insensitive regex search over the normalized answer. Anchor tokens
    with explicit word boundaries (\\b) so bare-substring false positives
    ('72' inside '727', 'angles' inside 'triangles') cannot pass."""
    f = norm(final)
    return any(re.search(pat, f, re.IGNORECASE) for pat in patterns)


def re_count(final, patterns):
    f = norm(final)
    return sum(1 for pat in patterns if re.search(pat, f, re.IGNORECASE))


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def date_in(final, date_text):
    """True when the answer states the given calendar date, tolerating
    'May 5, 2023' / 'May 5 2023' / 'May 5th, 2023' / '5 May 2023' / '05/05/2023'."""
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", date_text.strip())
    if not m:
        raise ValueError(f"date_in: unsupported date literal {date_text!r}")
    month, day, year = m.group(1).lower(), int(m.group(2)), m.group(3)
    if month not in _MONTHS:
        raise ValueError(f"date_in: unknown month {month!r}")
    mo = re.escape(month)
    md = f"0?{day}" if day >= 10 else f"0?{day}"
    f = norm(final)
    pats = [
        rf"\b{mo}\s+{md}(?:st|nd|rd|th)?\s*,?\s+{year}\b",        # May 5, 2023
        rf"\b{md}\s+(?:st|nd|rd|th)?\s+{mo}\s+{year}\b",         # 5 May 2023
        rf"\b{mo[:3]}\.?\s+{md}\s*,?\s+{year}\b",                # May 5, 2023 (abbrev ok)
        rf"\b{md}/0?{_MONTHS[month]}/{year}\b",                  # 5/5/2023
        rf"\b{year}-0?{_MONTHS[month]:02d}-{md}\b",              # 2023-05-05
    ]
    return any(re.search(p, f, re.IGNORECASE) for p in pats)


def _digit_forms(value):
    if abs(value - round(value)) > 1e-9:
        base = f"{value:.6f}".rstrip("0").rstrip(".")   # 9.58, 17.1, 2.4
        alt = f"{value:.1f}"                             # 9.6 (rounded form)
        forms = [base] if alt == base else [base, alt]
        return forms
    whole = str(int(round(value)))
    return [whole, f"{value:.1f}"]


def number_claim(final, value, unit_words=(), span=20):
    """True when the answer reports `value` as a standalone quantity, optionally
    requiring a unit word (players / members / meters / ...) within `span` chars
    after it. Commas inside digit groups ('19,847') are tolerated; ordinal
    suffixes ('45th') do NOT match."""
    f = re.sub(r"(?<=\d),(?=\d)", "", norm(final))
    for form in _digit_forms(value):
        for m in re.finditer(rf"(?<![\d.]){re.escape(form)}(?![\d])(?![a-z])", f):
            if not unit_words:
                return True
            tail = f[m.end(): m.end() + span]
            if any(w in tail for w in unit_words):
                return True
    return False


def _name_key(s):
    """Normalisation for name containment: casefold, & -> and, punctuation
    collapsed, whitespace collapsed, leading 'The' tolerated."""
    s = (s or "").casefold().replace("&", " and ")
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[.,;:!?()\[\]\"'#-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_in(final, name):
    """True when the answer names the entity (tolerating &/and, punctuation,
    and 'The' prefix differences)."""
    f = _name_key(final)
    n = _name_key(name)
    if not n:
        return False
    if n in f:
        return True
    if n.startswith("the ") and n[4:] in f:
        return True
    return False


def count_names(final, names):
    """How many of `names` the answer mentions."""
    return sum(1 for n in names if name_in(final, n))


def order_by_first_mention(final, table):
    """True when every entry the answer names appears in non-increasing `value`
    order (position of FIRST mention). `table` maps name -> value; ties may
    appear in any order. Used for 'sorted by rating / gross' list tasks."""
    f = _name_key(final)
    seen = []
    for name, value in table.items():
        key = _name_key(name)
        idx = f.find(key)
        if idx >= 0:
            seen.append((idx, value))
    seen.sort()
    values = [v for _, v in seen]
    return all(values[i] >= values[i + 1] for i in range(len(values) - 1))


# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state)."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{DB_FILENAME}"
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip()}")
    return path


def resolve_db(arg, container, kind):
    if arg:
        return arg
    try:
        return fetch_db(container, kind)
    except Exception:
        return None  # caller FAILs the check that needs it


def db_fingerprint(db_path, tables=CONTENT_TABLES):
    """Content fingerprint of the given tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in tables:
            try:
                rows = con.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def content_intact(initial_db, after_db):
    """True when the benchmark content tables are row-for-row identical between
    the seed state and the after state. None when a DB is unavailable."""
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None
    return a == b


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no-llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name   # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)


def parse_args():
    import simpleArgParser as sap

    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-google_search")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + content-DB integrity shared by every
    task in this file. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    intact = content_intact(init, after)
    if intact is None:
        judge.check("db_content_intact", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_content_intact", intact,
                    "content tables identical to seed" if intact
                    else "content tables differ from seed")
    return t, fa
