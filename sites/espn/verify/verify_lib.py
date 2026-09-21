#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for ESPN task verification.

Philosophy (same contract as the merriam_webster exemplar and the amazon /
allrecipes verify suites of this rollout): DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with a matching task id, a non-empty steps list whose
     referenced screenshots exist, and a non-empty final answer. Missing
     files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST
     have opened the on-site page(s) that carry the task's facts; a correct
     answer with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / number / score containment against ground truth
     hardcoded in each verify_<n>.py. Every ground-truth value was frozen
     from the served mirror pages (real-Chromium audit of container
     wh-ver-espn, image wh-pr114-ready); the mirror pins its clock to
     April 10, 2024 and has no wall-clock content.
  4. DB state check: all 44 ESPN tasks are read-only lookups, so an honest
     run leaves the instance DB identical to its seed snapshot. DBs are
     fetched with docker cp from the site container (default $WH_CONTAINER
     or wh-ver-espn), or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-espn)
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
import unicodedata
from dataclasses import dataclass
from pathlib import Path

SITE = "espn"
DB_FILENAME = "espn.db"

# Benchmark tables (content tables only; sqlite_sequence etc. excluded).
TABLES = ("users", "sports", "conferences", "divisions", "teams", "players",
          "player_stats", "games", "game_player_stats", "articles",
          "transactions", "depth_chart", "power_index", "recruits",
          "user_favorites")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """ESPN--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"ESPN--{m.group(1)}" if m else None


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


def visited_root(traj):
    """True when some step URL is the bare site origin (the mirror homepage)."""
    return any(re.match(r"^https?://[^/]+/?$", u) for u in step_urls(traj))


def visited_mirror_root(traj):
    """True when some step URL is the bare LOCAL mirror origin — the homepage
    of the site under test (any port; localhost / 127.0.0.1).  Off-site roots
    do not count, so a run that never opened the mirror FAILs homepage nav."""
    return any(re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?/?$", u)
               for u in step_urls(traj))


def first_mention(final, tokens):
    """Index (in the normalized answer) of the earliest occurrence among tokens,
    or None when none appears. Used for ordering-sensitive answers."""
    f = norm(final)
    idxs = [f.find(norm(t)) for t in tokens if f.find(norm(t)) >= 0]
    return min(idxs) if idxs else None


# ---------------------------------------------------------------- answer matching
def norm(s):
    """Lowercase, whitespace-folded, ASCII-folded form: 'Dončić' -> 'doncic',
    'Porziņģis' -> 'porzingis', 'Vinícius' -> 'vinicius'. Typographic dashes
    are first mapped to '-' so scorelines like '64–18' stay '64-18' (they would
    otherwise collapse to '6418' under plain ASCII folding)."""
    s = (s or "")
    for dash in ("\u2013", "\u2014", "\u2012", "\u2013", "\u2212", "\u2796"):
        s = s.replace(dash, "-")
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def num_in(final, number):
    """The integer `number` appears as a standalone number (word boundary),
    so 76 matches '76 games' but not '76ers'; 1 matches '1' / '1,' not '13'."""
    f = norm(final)
    return bool(re.search(rf"(?<![\d.]){number}(?![\d])", f))


def word_num_in(final, number, word=None):
    """num_in or the spelled-out word ('twelve', 'eight', 'one', ...). The
    spelled form defaults to the standard English word for `number`."""
    words = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
             11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
             15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
             19: "nineteen", 20: "twenty", 30: "thirty"}
    if word is None:
        word = words.get(number, "")
    return num_in(final, number) or (word != "" and word in norm(final))


def score_pair_in(final, a, b):
    """Both scores of a game appear, either as '119-114' / '119 - 114' style or
    as standalone numbers somewhere in the answer."""
    f = norm(final)
    if re.search(rf"(?<![\d.]){a}\s*[-–to]\s*{b}(?![\d])", f):
        return True
    return num_in(final, a) and num_in(final, b)


def scoreline_in(final, a, b):
    """The scoreline 'a-b' (or 'b-a', or comma form) appears literally — used for
    low scores where bare number pairs are too weak (e.g. NHL 2-4)."""
    f = norm(final)
    for x, y in ((a, b), (b, a)):
        if re.search(rf"(?<![\d.]){x}\s*[-–,]\s*{y}(?![\d])", f):
            return True
    return False


def game_score_in(final, a, b):
    """Game score match: for two-digit scores accept a scoreline or both numbers;
    for low scores (NHL/soccer) require the literal scoreline in either order."""
    if a >= 10 and b >= 10:
        return score_pair_in(final, a, b)
    return scoreline_in(final, a, b)


def word_in(final, word):
    """The word appears with word boundaries (so 'out' matches 'ruled OUT' but
    not 'about')."""
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(norm(word))}(?![a-z0-9])", norm(final)))


def dollar_in(final, amount):
    """A dollar amount appears: 55 matches '$55', '55.00', '55 dollars',
    'USD 55'; 36,000,000 matches '36,000,000', '$36M', '36 million', '36000000'."""
    f = norm(final)
    if isinstance(amount, int) and amount >= 1000000:
        plain = f"{amount:,}"
        if plain in f or str(amount) in f:
            return True
        millions = amount // 1000000
        if re.search(rf"(?<![\d.]){millions}(?![\d])\s*m\b", f):
            return True
        if re.search(rf"(?<![\d.]){millions}(?![\d])\s*million", f):
            return True
        return False
    return bool(re.search(rf"(?<![\d.]){amount}(?![\d])", f))


def pos_in(final, positions):
    """A basketball/football position appears as a standalone token or phrase:
    PF/'power forward', C/'center', PG/'point guard', SF/'small forward',
    SG/'shooting guard', or the bare position letters with boundaries."""
    f = norm(final)
    phrases = {"pf": ["pf", "power forward"], "c": ["center", "centre"],
               "pg": ["pg", "point guard"], "sf": ["sf", "small forward", "forward"],
               "sg": ["sg", "shooting guard", "guard"], "g": ["guard"],
               "f": ["forward"], "wr": ["wr", "wide receiver"], "rb": ["rb", "running back"],
               "qb": ["qb", "quarterback"]}
    for p in positions:
        for token in phrases.get(p, [p]):
            if token in ("c", "pg", "sf", "sg", "pf", "wr", "rb", "qb", "g", "f"):
                if re.search(rf"(?<![a-z0-9]){token}(?![a-z0-9])", f):
                    return True
            else:
                if token in f:
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
    """Content fingerprint of the benchmark tables: (rows, sha16) per table."""
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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-espn")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + read-only DB check shared by every task.
    Returns (traj, final_answer). All 44 ESPN tasks are read-only lookups, so an
    honest run leaves the instance DB identical to its seed snapshot."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    if ro is None:
        judge.check("db_state_readonly", False,
                    "initial/after DB unavailable (container not running? pass --initial_db/--after_db)")
    else:
        judge.check("db_state_readonly", ro,
                    "instance DB identical to seed (read-only task)" if ro
                    else "instance DB differs from seed (task is read-only)")
    return t, fa
