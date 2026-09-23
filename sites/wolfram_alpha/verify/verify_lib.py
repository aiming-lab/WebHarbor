#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Wolfram Alpha task verification.

Philosophy (same contract as the merriam_webster / huggingface exemplars):
DETERMINISTIC FIRST, no LLM anywhere in this suite.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an http(s) start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST
     have submitted a computation query on the mirror's /input endpoint whose
     text carries the task's mathematical core AND avoids the per-record
     verbose-wording rejections the mirror itself enforces (the seed's
     `required_specifiers` negative gates: "what is the", "find the",
     "when x =", "show me", ...). A correct answer with no matching /input
     query is a memory-recall shortcut = FAIL.
  3. Answer check: token / decimal containment against ground truth hardcoded
     in each verify_<n>.py. Ground truth was read off the served mirror pages
     with a real Chromium during the reviewer audit
     (reports/wolfram_alpha/audit/); the computation catalog is fixed by the
     seed DB, so no wall-clock or upstream content is involved.
  4. DB state check: every task in this file is read-only on the site, so an
     honest run leaves the user-state tables (users, saved_queries, notebooks,
     notebook_entries, favorites, query_history, topic_feedback) identical to
     the seed snapshot. Topic view_count is excluded on purpose: viewing a
     /topic/<slug> page legitimately increments it. DBs are fetched with
     docker cp from the site container (default $WH_CONTAINER or
     wh-ver-wolfram_alpha), or passed explicitly via --initial_db/--after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-wolfram_alpha)
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
from urllib.parse import urlparse, parse_qs, unquote

SITE = "wolfram_alpha"
DB_FILENAME = "wolfram_alpha.db"
TASK_PREFIX = "Wolfram Alpha"

# User-state tables an honest anonymous run must never write. topics.view_count
# is intentionally excluded: opening /topic/<slug> legitimately increments it.
USER_STATE_TABLES = ("users", "saved_queries", "notebooks", "notebook_entries",
                     "favorites", "query_history", "topic_feedback")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """'Wolfram Alpha--<n>' inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{TASK_PREFIX}--{m.group(1)}" if m else None


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
        if not s.get("url"):
            raise RunPackageError(f"step {i} has no url")
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
    """Every recorded step URL, in chronological order."""
    out = []
    for s in traj.get("steps", []):
        u = s.get("url")
        if isinstance(u, str) and u:
            out.append(u)
    return out


def input_queries(traj):
    """Decoded `i` params of every /input computation submission in the
    trajectory, in chronological order (deduped). Same-origin only: an
    /input URL on a host other than the run's start_url origin (e.g. the
    real upstream wolframalpha.com) is NOT on-site navigation and is
    filtered out; relative /input paths are accepted."""
    allowed_host = urlparse(traj.get("start_url") or "").netloc
    out = []
    for u in step_urls(traj):
        try:
            p = urlparse(u)
        except Exception:
            continue
        if p.path.rstrip("/") != "/input":
            continue
        if p.netloc and allowed_host and p.netloc != allowed_host:
            continue  # off-site /input is not mirror navigation
        vals = parse_qs(p.query).get("i") or []
        for v in vals:
            v = unquote(v)
            if v and v not in out:
                out.append(v)
    return out


# Math-adjacent normalization for robust substring matching:
#   casefold + accent fold, superscript runs -> ^<run> (incl. the superscript
#   minus, so 10⁻⁸ -> 10^-8), unicode minus -> -, multiplication dots -> *,
#   pi/sqrt glyphs, digit-group separators ("," or " " between digits)
#   removed, all whitespace collapsed then removed.
_SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                 "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
                 "⁻": "-"}


def _superscript_run(match):
    return "^" + "".join(_SUPERSCRIPTS.get(c, c) for c in match.group(0))


def math_norm(s):
    s = (s or "").casefold()
    # superscript runs must be folded BEFORE NFKD (NFKD decomposes them away)
    s = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+", _superscript_run, s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = (s.replace("−", "-").replace("–", "-").replace("×", "*")
          .replace("·", "*").replace("⋅", "*").replace("π", "pi")
          .replace("√", "sqrt").replace("≈", "~").replace("⁄", "/"))
    # strip commas and spaces used as digit group separators: 1,184.54 / 186 313
    s = re.sub(r"(?<=\d)[,\s](?=\d)", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" ", "")


def norm(s):
    """Plain text normalization (whitespace collapse only)."""
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def contains_all(final, tokens):
    f = math_norm(final)
    return all(math_norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = math_norm(final)
    return any(math_norm(t) in f for t in tokens)


def count_named(final, names):
    """How many of `names` appear in the answer (math-normalized)."""
    f = math_norm(final)
    return sum(1 for n in names if math_norm(n) in f)


_BOUND_SPLIT = re.compile(r"[;\n,]|\band\b|\bwhile\b|\bwhereas\b")


def bound(final, anchors, values):
    """Clause-level value-attribution binding: true iff some clause of the
    final answer (clauses are split on ';', newlines and the word 'and'
    BEFORE normalization) contains one of `anchors` together with one of
    `values` (both math-normalized inside the clause). This rejects
    swapped-attribution answers: the right numbers attached to the wrong
    entity do not bind."""
    for c in _BOUND_SPLIT.split(final or ""):
        n = math_norm(c)
        if any(math_norm(a) in n for a in anchors) and \
           any(math_norm(v) in n for v in values):
            return True
    return False


def bound_nearest(final, anchors, values, other_anchors=(), other_values=()):
    """Position-based value-attribution binding: each value occurrence binds
    to its nearest PRECEDING anchor interval and/or its nearest FOLLOWING
    anchor interval. True iff some occurrence of one of `values` binds to
    one of `anchors` in either direction. Handles 'name: value' bullets,
    comma-separated 'name value' chains, prose ('Providence averaged $14.37')
    and 'value for name' pods ('$14.37 for Providence'), while rejecting
    swapped attributions in value-after-name and value-for-name layouts."""
    f = math_norm(final)

    def spans(tok):
        return [m.span() for m in re.finditer(re.escape(math_norm(tok)), f)]

    all_anchors = [(s, e, True) for a in anchors for (s, e) in spans(a)] + \
                   [(s, e, False) for a in other_anchors for (s, e) in spans(a)]
    if not all_anchors:
        return False
    for v in values:
        for (vs, ve) in spans(v):
            before = [(vs - e, own) for (s, e, own) in all_anchors if e <= vs]
            after = [(s - ve, own) for (s, e, own) in all_anchors if s >= ve]
            for _, own in ([min(before, key=lambda x: (x[0], x[1]))] if before else []) + \
                          ([min(after, key=lambda x: (x[0], x[1]))] if after else []):
                if own:
                    return True
    return False


def bound_preceding(final, anchors, values, other_anchors=()):
    """Preceding-first value-attribution binding: each value occurrence
    binds to its nearest PRECEDING anchor interval; only when no anchor
    precedes it does it bind to the nearest FOLLOWING one. True iff some
    occurrence of one of `values` binds to one of `anchors`. Use for
    'name: value' layouts where a following-anchor fallback must not
    rescue a swapped attribution that already has a (wrong) preceding
    anchor (contrast with bound_nearest, which accepts both directions)."""
    f = math_norm(final)

    def spans(tok):
        return [m.span() for m in re.finditer(re.escape(math_norm(tok)), f)]

    all_anchors = [(s, e, True) for a in anchors for (s, e) in spans(a)] + \
                  [(s, e, False) for a in other_anchors for (s, e) in spans(a)]
    if not all_anchors:
        return False
    for v in values:
        for (vs, ve) in spans(v):
            before = [(vs - e, own) for (s, e, own) in all_anchors if e <= vs]
            after = [(s - ve, own) for (s, e, own) in all_anchors if s >= ve]
            if before:
                _, own = min(before, key=lambda x: (x[0], x[1]))
            elif after:
                _, own = min(after, key=lambda x: (x[0], x[1]))
            else:
                continue
            if own:
                return True
    return False


def in_order(final, token_groups):
    """True iff the answer carries the given token groups in sequence:
    some occurrence of any alternative of group 0, then (strictly after it)
    some occurrence of any alternative of group 1, and so on. Alternatives
    are math-normalized; purely numeric alternatives are matched with
    digit-boundaries so '17' does not match inside '117' or '17.5'."""
    f = math_norm(final)
    pos = 0
    for alts in token_groups:
        found = None
        for alt in alts:
            pat = re.escape(math_norm(alt))
            if re.fullmatch(r"\d+(?:\.\d+)?", math_norm(alt)):
                pat = r"(?<![\d.])" + pat + r"(?![\d.])"
            m = re.compile(pat).search(f, pos)
            if m and (found is None or m.start() < found[0]):
                found = (m.start(), m.end())
        if not found:
            return False
        pos = found[1]
    return True


def value_unit(final, values, units, gap=2):
    """True iff some occurrence of one of `values` is directly followed by
    one of `units` (the unit token must start within `gap` characters of
    the value's end — normalization has already removed spaces), so the
    unit attaches to THAT value and a restated task parameter elsewhere
    in the answer cannot satisfy the binding. Both sides math-normalized."""
    f = math_norm(final)
    for v in values:
        for m in re.finditer(r"(?<![\d.])" + re.escape(math_norm(v)) + r"(?![\d.])", f):
            for u in units:
                un = math_norm(u)
                if any(f[m.end() + g:].startswith(un) for g in range(gap + 1)):
                    return True
    return False


def decimal_in(final, value, tol=0.0):
    """True when the answer carries the decimal `value` as a standalone number
    (word-boundary match so '128.5' does not satisfy '28.5'); with tol, any
    decimal within +/- tol also passes. Digit-group separators were already
    folded by math_norm."""
    f = math_norm(final)
    v = str(value)
    if re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", f):
        return True
    if tol:
        for m in re.finditer(r"-?\d+(?:\.\d+)?", f):
            try:
                if abs(float(m.group(0)) - float(v)) <= tol:
                    return True
            except ValueError:
                continue
    return False


def queried_with_all(traj, must_all=(), any_of=(), forbidden=()):
    """True when at least one /input query in the trajectory contains every
    token of `must_all` (AND), at least one token of each group in `any_of`
    (list of alternative-sets), and none of `forbidden`. Matching is
    math-normalized substring matching."""
    for q in input_queries(traj):
        n = math_norm(q)
        if all(math_norm(t) in n for t in must_all):
            if all(any(math_norm(a) in n for a in alts) for alts in any_of):
                if not any(math_norm(f) in n for f in forbidden):
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


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def user_state_fingerprint(db_path):
    """Content fingerprint of the user-state tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in USER_STATE_TABLES:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def user_state_delta(initial_db, after_db):
    """Strict read-only classification over the user-state tables: ok=True only
    when the after DB matches the seed state. None when either DB unavailable."""
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable"
    a = user_state_fingerprint(initial_db)
    b = user_state_fingerprint(after_db)
    if a is None or b is None:
        return None, "initial/after DB unavailable"
    if a == b:
        return True, "user-state tables identical to seed"
    return False, "user-state tables differ from seed (no task in this file may write state)"


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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-wolfram_alpha")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + read-only user-state DB check shared
    by every task in this file. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok, detail = user_state_delta(init, after)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa
