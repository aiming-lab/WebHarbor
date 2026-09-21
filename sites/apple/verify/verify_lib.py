#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Apple task verification.

Philosophy (same contract as the merriam_webster / phet_simulations / amazon
exemplars): DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / price / count containment against ground truth
     hardcoded in each verify_<n>.py. Every ground-truth value below was
     confirmed on the served pages of the running mirror container (the
     catalog is fixed by the instance_seed DB; the mirror has no wall-clock or
     upstream-fed content).
  4. DB state check: every task in this file is read-only on the mirror (the
     in-store pickup confirmation is a GET-parameter state, the anonymous bag
     is cookie-backed, and no task row carries login credentials), so an
     honest run leaves the instance DB identical to its seed snapshot. DBs
     are fetched with docker cp from the site container (default $WH_CONTAINER
     or wh-ver-apple), or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   container to fetch DBs from (default: $WH_CONTAINER or wh-ver-apple)
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
from urllib.parse import urlsplit, parse_qsl

SITE = "apple"
DB_FILENAME = "apple_store.db"
# SQLAlchemy default table names (singular); "order" is quoted at use sites.
TABLES = ("cart_item", "order", "order_item", "payment_methods", "product",
          "review", "saved_addresses", "support_article", "trade_in_value",
          "user", "wishlist_item")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """Apple--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{SITE.title()}--{m.group(1)}" if m else None


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


def url_path(url):
    """Normalized path (no query/fragment, no trailing slash) of a step URL."""
    try:
        path = urlsplit(url).path or "/"
    except Exception:
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def navigated_path(traj, path):
    """Exact-path navigation: some step URL's path equals `path` (trailing slash tolerated)."""
    want = path.rstrip("/") or "/"
    return any(url_path(u) == want for u in step_urls(traj))


def navigated_paths_all(traj, paths):
    """True when every path in `paths` was visited (exact-path match)."""
    return all(navigated_path(traj, p) for p in paths)


def url_query(url):
    """Decoded query dict (first value wins) of a step URL."""
    try:
        q = urlsplit(url).query
    except Exception:
        return {}
    out = {}
    for k, v in parse_qsl(q or "", keep_blank_values=True):
        out.setdefault(k, v)
    return out


def visited_url_with(traj, substr, params_sub=None, params_exact=None):
    """True when some visited URL contains `substr` (case-insensitive) AND every
    (key, value-substring) pair in params_sub is satisfied by its decoded query
    AND every (key, value) pair in params_exact matches exactly (case-insensitive).
    params_sub/params_exact are sequences of (key, value) tuples."""
    needle = substr.lower()
    for u in step_urls(traj):
        if needle not in u.lower():
            continue
        q = url_query(u)
        if params_sub and not all(k in q and v.lower() in q[k].lower()
                                  for k, v in params_sub):
            continue
        if params_exact and not all(k in q and q[k].strip().lower() == v.strip().lower()
                                    for k, v in params_exact):
            continue
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


def contains_word(final, word):
    """Word-boundary containment: '16gb' matches '16GB' or '16 GB' but a bare
    '10' does not match inside '2024'."""
    return re.search(rf"(?<![0-9A-Za-z]){re.escape(norm(word))}(?![0-9A-Za-z])",
                     norm(final)) is not None


def contains_words_any(final, words):
    return any(contains_word(final, w) for w in words)


def price_in(final, price):
    """True when the answer mentions the given price, with the cents part when
    it is not integral: 64.99 matches '$64.99' / '64.99' / 'USD 64.99';
    1299.00 matches '1299.00', '$1299', '$1,299', '1299 dollars', or bare '1299'.
    Thousands separators between digits ('$1,099') are stripped before the
    match, mirroring how the site and agents format US prices."""
    f = norm(final)
    f = re.sub(r"(?<=\d),(?=\d)", "", f)   # $1,099 -> $1099
    if abs(price - round(price)) > 1e-9:
        txt = f"{price:.2f}"
        return txt in f or txt.rstrip("0").rstrip(".") in f
    whole = str(int(round(price)))
    return bool(re.search(r"(?<![\d.])" + whole + r"(?![\d])", f)) or f"{whole}.00" in f


def count_named(final, tokens):
    """How many distinct tokens from `tokens` appear in the answer."""
    return sum(1 for t in tokens if contains_any(final, [t]))


def number_claim(final, number, words):
    """True when the answer claims `number` of `word` (word forms listed), e.g.
    '4 colors', 'four colors', 'colors: 4'. Word-boundary on the numeral."""
    f = norm(final)
    for w in words:
        if re.search(rf"(?<![\d.]){number}(?![\d])(\s+[a-z-]+){{0,3}}\s+{w}s?\b", f):
            return True
        if re.search(rf"{w}s?[^.;]{{0,20}}(?<![\d.]){number}(?![\d])", f):
            return True
    return False


def is_jan10_2024(datestr):
    """Accept the on-page / form encodings of the January 10, 2024 pickup date."""
    s = norm(datestr).replace("  ", " ").strip().rstrip(".")
    if re.fullmatch(r"2024-0?1-0?10", s):
        return True
    if re.fullmatch(r"0?1/0?10/2024", s):
        return True
    if re.fullmatch(r"jan(uary)?\.?\s+0?10,?\s+2024", s):
        return True
    return False


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
                rows = con.execute(f'SELECT * FROM "{t}"').fetchall()
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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-apple")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + strict read-only DB check shared by every
    task (no apple task writes the DB: pickup confirmation is GET-parameter state,
    the anonymous bag is cookie-backed, and no task row carries login credentials).
    Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok = read_only_run(init, after)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok,
                    "after-state DB identical to seed" if ok
                    else "after-state DB differs from seed")
    return t, fa
