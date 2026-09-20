#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Google Map task verification.

Philosophy (same contract as the merriam_webster / phet_simulations / amazon
exemplars): DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: name / token / number / ordering containment against ground
     truth hardcoded in each verify_<n>.py (ground truth confirmed by browsing
     the served mirror pages with a real Chromium; the catalog is fixed by the
     seed DB and the mirror has no wall-clock content).
  4. DB state check: every task in this task file is read-only on the DB
     (no login, save, review, or trip is asked for), so an honest run leaves
     the instance DB identical to its seed snapshot. DBs are fetched with
     docker cp from the site container (default $WH_CONTAINER or
     wh-ver-google_map), or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   container to fetch DBs from (default: $WH_CONTAINER or wh-ver-google_map)
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

SITE = "google_map"
TASK_PREFIX = "Google Map--"
DB_FILENAME = "gmaps.db"

TABLES = ("user", "category", "city", "route", "place", "saved_list", "trip",
          "saved_place", "trip_stop", "review", "photo", "timeline_entry")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """'Google Map--<n>' inferred from the verify_<n>.py entry-point filename."""
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


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on recorded step URLs."""
    needle = substr.lower()
    return sum(1 for u in step_urls(traj) if needle in u.lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def navigated_phrase(traj, phrase):
    """Navigation check for a multi-word query phrase: matches the phrase with
    spaces, '+'-encoded, %-20-encoded, or '-'-joined separators (agent search
    URLs may use either encoding; place-page slugs join words with '-')."""
    words = phrase.lower().split()
    variants = [phrase.lower(), "+".join(words), "%20".join(words),
                "-".join(words), "%2b".join(words)]
    return navigated_any(traj, variants)


def visited_place(traj, slug):
    return navigated_to(traj, f"/place/{slug}")


def visited_any_place(traj, slugs):
    return any(visited_place(traj, s) for s in slugs)


# ---------------------------------------------------------------- answer matching
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _name_key(s):
    """Normalisation for place-name containment: casefold, & -> and,
    punctuation collapsed, whitespace collapsed."""
    s = (s or "").casefold().replace("&", " and ")
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[.,;:!?()\[\]\"'#-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_in(final, name):
    """True when the answer names the place (tolerating &/and, punctuation,
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


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def re_any(final, patterns):
    """Case-insensitive regex search over the normalized answer. The caller
    anchors tokens with explicit word boundaries (\\b) so bare-substring
    false positives (e.g. 'mexico' inside 'Gulf of Mexico', 'closes' inside
    'never closes') cannot pass; use this for fact checks where the answer
    must match a page phrase, not just share a token."""
    f = norm(final)
    return any(re.search(pat, f, re.IGNORECASE) for pat in patterns)


def re_count(final, patterns):
    """Count of caller-anchored regex patterns that match the answer."""
    f = norm(final)
    return sum(1 for pat in patterns if re.search(pat, f, re.IGNORECASE))


def _digit_forms(value):
    if abs(value - round(value)) > 1e-9:
        return [f"{value:.1f}".rstrip("0").rstrip("."), f"{value:.1f}"]
    whole = str(int(round(value)))
    return [whole, f"{value:.1f}"]


def number_claim(final, value, unit_words=(), span=18):
    """True when the answer reports `value` as a standalone quantity, optionally
    requiring a unit word (mi / min / hours / ...) within `span` chars after it.
    Commas inside digit groups ('1,742') are tolerated; ordinal suffixes
    ('45th') do NOT match. 45.0 also matches a plain '45' claim."""
    f = re.sub(r"(?<=\d),(?=\d)", "", norm(final))
    for form in _digit_forms(value):
        for m in re.finditer(rf"(?<![\d.]){re.escape(form)}(?![\d])(?![a-z])", f):
            if not unit_words:
                return True
            tail = f[m.end(): m.end() + span]
            if any(w in tail for w in unit_words):
                return True
    return False


def distance_claim(final, miles):
    """Distance claim: '0.7 mi', '45 miles', '~2.3mi', '1742 mi', '1,742 mi'."""
    return number_claim(final, miles, unit_words=("mi", "mile"))


def minutes_claim(final, mins):
    """Duration claim: '14 min', '54 minutes', '~7-min', '8 min walk'."""
    return number_claim(final, mins, unit_words=("min", "minute"))


def rating_order_ok(final, table):
    """True when every table entry the answer names appears in non-increasing
    rating order (position of FIRST mention). `table` maps name -> rating.
    Ties (equal ratings) may appear in any order."""
    f = _name_key(final)
    seen = []
    for name, rating in table.items():
        key = _name_key(name)
        idx = f.find(key)
        if idx >= 0:
            seen.append((idx, rating))
    seen.sort()
    ratings = [r for _, r in seen]
    return all(ratings[i] >= ratings[i + 1] for i in range(len(ratings) - 1))


def extract_mi_values(final):
    """Every 'N mi' / 'N miles' number in the answer, as floats."""
    f = norm(final)
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:mi|miles|mile)\b", f):
        out.append(float(m.group(1)))
    return out


def numbers_in(text):
    """Integers in the answer, as digits or as English number words 0-20."""
    out = [int(m.replace(",", "")) for m in re.findall(r"\b\d[\d,]*\b", text or "")]
    words = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
             "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
             "nineteen": 19, "twenty": 20}
    for w, v in words.items():
        if re.search(rf"\b{w}\b", (text or ""), re.IGNORECASE):
            out.append(v)
    return out


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


def db_fingerprint(db_path):
    """Content fingerprint of the benchmark tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in TABLES:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def read_only_run(initial_db, after_db):
    """True when the after-state DB is row-for-row identical to the seed state.
    None when either DB is unavailable."""
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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-google_map")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + read-only DB check shared by every
    task in this file. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    if ro is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ro,
                    "read-only run: instance DB identical to seed" if ro
                    else "instance DB differs from seed")
    return t, fa
