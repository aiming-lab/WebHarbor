#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for GitHub task verification.

Philosophy (same contract as the merriam_webster / phet_simulations / amazon
exemplars): DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with a matching task id, a non-empty steps list whose
     referenced screenshots exist, an http(s) start URL, and a non-empty final
     answer. Missing files / missing trajectory / empty answer => FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / number / date / repo-name containment against ground
     truth hardcoded in each verify_<n>.py. Ground truth was read off the served
     pages of the running mirror container (the catalog is fixed by the seed
     DB; every "last N days" filter is anchored to the site's frozen date
     2024-05-15, shown on every page), never from upstream internet.
  4. DB state check: every task in this file is read-only on the DB except the
     sign-up check (task 40), which may add one user row for the queried email.
     DBs are fetched with docker cp from the site container (default
     $WH_CONTAINER or wh-ver-github), or passed via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   container to fetch DBs from (default: $WH_CONTAINER or wh-ver-github)
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
from urllib.parse import unquote_plus

SITE = "github"
DB_FILENAME = "github_mirror.db"

# Every mutable runtime table; the catalog tables are included too so any
# accidental write (star toggle, profile edit) fails the read-only check.
TABLES = ("user", "repository", "topic", "repo_topics", "star", "watch",
          "follows", "issue", "issue_comment")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """GitHub--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"GitHub--{m.group(1)}" if m else None


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

    # every recorded step must stay on the mirror origin (anti upstream-shortcut:
    # a run that answers from the real github.com is not a mirror solve)
    from urllib.parse import urlparse
    start_loc = urlparse(start_url)
    origin = (start_loc.scheme, start_loc.netloc)

    def _origin_ok(url):
        if not isinstance(url, str) or not url:
            return True  # missing fields are handled by the steps loop below
        loc = urlparse(url)
        return (loc.scheme, loc.netloc) == origin

    for i, s in enumerate(traj.get("steps") or []):
        if isinstance(s, dict):
            for field in ("url", "url_after"):
                u = s.get(field)
                if isinstance(u, str) and u and not _origin_ok(u):
                    raise RunPackageError(
                        f"step {i} {field} navigated off the mirror origin: {u!r}")
    fu = traj.get("final_url")
    if isinstance(fu, str) and fu and not _origin_ok(fu):
        raise RunPackageError(f"final_url navigated off the mirror origin: {fu!r}")

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
    """Every recorded step URL (before + after the action) plus final_url."""
    out = []
    for s in traj.get("steps", []):
        for field in ("url", "url_after"):
            u = s.get(field)
            if isinstance(u, str) and u:
                out.append(u)
    fu = traj.get("final_url")
    if isinstance(fu, str) and fu:
        out.append(fu)
    return out


def decoded(url):
    """Query-decoded URL: '+' forms and %XX escapes become plain text so
    substring checks see 'language:python updated:>2024-05-13' etc."""
    return unquote_plus(url)


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on decoded recorded step URLs."""
    needle = substr.lower()
    return sum(1 for u in step_urls(traj) if needle in decoded(u).lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def visited_repo(traj, full_name):
    """True when a step URL opens the repo page /<owner>/<repo>."""
    return navigated_to(traj, f"/{full_name.lower()}")


def visited_repo_any(traj, full_names):
    return any(visited_repo(traj, fn) for fn in full_names)


def search_url_with(traj, must_have_all):
    """True when some visited /search URL's decoded form contains every
    required substring (e.g. ['python', 'updated', 'stars'])."""
    for u in step_urls(traj):
        if "/search" not in u:
            continue
        d = decoded(u).lower()
        if all(m.lower() in d for m in must_have_all):
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


def _repo_regex(repo_part):
    """Match a repo name flexibly: hyphens/underscores as separators or absent,
    so 'xgboost-trees', 'xgboost trees' and 'xgboosttrees' all match."""
    parts = [re.escape(p) for p in re.split(r"[-_]", repo_part)]
    return re.compile(r"[\s_-]*".join(parts), re.IGNORECASE)


def mentions_repo(final, full_name, owner_required=False):
    """True when the answer names the repository. Accepts 'owner/repo',
    'repo', and separator-varied spellings ('xgboost trees')."""
    f = norm(final)
    owner, _, repo = full_name.partition("/")
    if re.search(rf"(?<![\w.-]){re.escape(owner)}[\s/_.-]+{_repo_regex(repo).pattern}(?![\w-])", f):
        return True
    if owner_required:
        return False
    return bool(re.search(rf"(?<![\w.-]){_repo_regex(repo).pattern}(?![\w-])", f))


def mentions_any_repo(final, full_names):
    """Return the first full_name (in the given order) the answer names, else None."""
    for fn in full_names:
        if mentions_repo(final, fn):
            return fn
    return None


_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def numbers_in(text):
    """Integers in the answer, as digits or as English number words."""
    out = [int(m.replace(",", "")) for m in re.findall(r"\b\d[\d,]*\b", text or "")]
    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", text or "", re.IGNORECASE):
            out.append(value)
    return out


def has_number(text, value):
    return value in numbers_in(text)


def counts(text, value, *nouns):
    """True when `value` is reported AS A COUNT of one of `nouns`
    ('4 courses', 'four courses', 'courses: 4', 'contains 4')."""
    t = (text or "").lower()
    if value not in numbers_in(text):
        return False
    words = {v: k for k, v in _WORD_NUMBERS.items()}
    forms = [str(value)] + ([words[value]] if value in words else [])
    for noun in [n.lower() for n in nouns]:
        for f in forms:
            pats = [rf"{re.escape(f)}\s*(?:\w+\s+){{0,3}}{re.escape(noun)}",
                    rf"{re.escape(noun)}[^.]{{0,40}}?\b{re.escape(f)}\b"]
            if any(re.search(p, t) for p in pats):
                return True
    return False


def figure_mentioned(final, kstr, full=None):
    """True when the answer cites a served figure in any of its forms.
    kstr is the k-notation string shown on the mirror ('12.8', '185', '2.2');
    full is the equivalent integer ('12,800', '185,000', '2,200'). Accepts
    '12.8k', '12.8 k', '185.0k', '185k', '12,800', '12800'."""
    f = norm(final)
    kesc = re.escape(kstr)
    if re.search(rf"(?<![\d.,]){kesc}(?:\.0)?\s?k(?![a-z0-9])", f):
        return True
    if full is not None:
        s = str(full)
        if re.search(rf"(?<![\d.,]){s}(?![\d])", f):
            return True
        head, tail = s[:-3], s[-3:]
        if len(s) > 3 and re.search(rf"(?<![\d.,]){head},{tail}(?![\d])", f):
            return True
    return False


def dates_in(text):
    """ISO and common long-form dates, normalised to YYYY-MM-DD where possible."""
    out = list(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text or ""))
    months = {m: f"{i+1:02d}" for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"])}
    for mon, day, year in re.findall(
            r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", text or ""):
        key = mon.casefold()
        if key in months:
            out.append(f"{year}-{months[key]}-{int(day):02d}")
    for day, mon, year in re.findall(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", text or ""):
        key = mon.casefold()
        if key in months:
            out.append(f"{year}-{months[key]}-{int(day):02d}")
    return out


def mentions_date(final, iso_date):
    return iso_date in dates_in(final)


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
    """Row-content fingerprint of every mutable table: (rows, sha256)."""
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
    """True when the after-state DB is row-identical to the seed state.
    None when either DB is unavailable."""
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None
    return a == b


def db_delta(initial_db, after_db, allowed_new_user_email=None):
    """Classify the DB delta of a run against the seed state.

    Returns (ok, detail). ok=True when the only difference is new `user` rows
    whose email equals allowed_new_user_email (the sign-up flow the task
    invites); every other change is a violation. None-detail when either DB is
    unavailable."""
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable"
    violations = []
    allowed = 0
    for table in TABLES:
        con_a = sqlite3.connect(initial_db)
        con_b = sqlite3.connect(after_db)
        try:
            try:
                before = con_a.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.Error:
                before = []
            try:
                after = con_b.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.Error:
                after = []
        finally:
            con_a.close()
            con_b.close()
        if before == after:
            continue
        bset = {repr(r) for r in before}
        aset = {repr(r) for r in after}
        removed = [r for r in before if repr(r) not in aset]
        added = [r for r in after if repr(r) not in bset]
        if removed:
            violations.append(f"{table}: {len(removed)} row(s) removed/changed")
        if not added:
            continue
        if table == "user" and allowed_new_user_email:
            for row in added:
                email = row[2] if len(row) > 2 else None  # id, username, email
                if isinstance(email, str) and email.strip().lower() == allowed_new_user_email.lower():
                    allowed += 1
                else:
                    violations.append(f"user: added row {email!r} (not the queried sign-up email)")
        else:
            violations.append(f"{table}: {len(added)} row(s) added (no table writes allowed)")
    if violations:
        return False, "; ".join(violations)[:300]
    if allowed:
        return True, f"db = seed + {allowed} new user row(s) for {allowed_new_user_email}"
    return True, "db identical to seed"


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-github")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a, allowed_new_user_email=None):
    """Package gate + non-empty answer + DB-state check shared by every task.
    Returns (traj, final_answer). The DB check is strict read-only unless the
    task passes an allowed sign-up email (task 40 only)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok, detail = db_delta(init, after, allowed_new_user_email)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa
