#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Booking task verification.

Philosophy (same contract as the merriam_webster / amazon exemplars):
DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / price / count containment against ground truth
     hardcoded in each verify_<n>.py. Ground truth was confirmed by browsing
     the served pages of the running container; the catalog is fixed by the
     seed DB and the mirror has no wall-clock content.
  4. DB state check: read-only tasks require the instance DB to be identical to
     its seed snapshot. The four booking tasks (6, 11, 13, 14) additionally
     accept a cart/booking delta for the task's allowed property set with the
     task's dates; every other mutation is a violation. DBs are fetched with
     docker cp from the site container (default $WH_CONTAINER or
     wh-ver-booking), or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-booking)
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

SITE = "booking"
DB_FILENAME = "booking.db"

# All benchmark tables in the instance DB. The verifiers compare row content
# across these tables between the initial (seed) and after snapshots.
TABLES = ("user", "city", "dest_category", "property_type", "property",
          "landmark", "review", "payment_methods", "booking", "booking_item",
          "cart_item", "saved_property")

# Demo account the login page publishes (tasks 6/11/13/14 may book under it).
DEMO_USER_EMAIL = "sophie.m@test.com"
DEMO_USER_ID = 2


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """Booking--<n> inferred from the verify_<n>.py entry-point filename."""
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
def _urlnorm(u):
    """Normalize a recorded URL for matching: form submissions encode spaces as
    '+' (or %20), while the check strings use plain spaces."""
    return (u or "").replace("%20", " ").replace("+", " ")


def _needlenorm(s):
    return (s or "").replace("%20", " ").replace("+", " ")


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
    """Case-insensitive substring match on recorded step URLs (space-normalized)."""
    needle = _needlenorm(substr).lower()
    return sum(1 for u in step_urls(traj) if needle in _urlnorm(u).lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def visited_property(traj, slug):
    return navigated_to(traj, f"/property/{slug}")


def visited_root(traj):
    """True when some step URL is the bare site origin (the mirror homepage)."""
    return any(re.match(r"^https?://[^/]+/?$", u) for u in step_urls(traj))


def search_url_with(traj, must_have_all):
    """True when some visited URL is a /search page whose query string contains
    every required param substring (e.g. ['q=london', 'breakfast=1']). Spaces in
    the check strings match URL-encoded '+' or %20."""
    for u in step_urls(traj):
        if "/search" not in u:
            continue
        nu = _urlnorm(u).lower()
        if all(_needlenorm(m).lower() in nu for m in must_have_all):
            return True
    return False


# ---------------------------------------------------------------- answer matching
def norm(s):
    """Normalize text for matching: collapse whitespace, casefold, and fold the
    typographic variants agents type (en/em dashes -> '-', curly quotes -> "',
    nbsp -> space) so 'The Lana – Dorchester Collection' matches the catalog's
    'The Lana - Dorchester Collection'."""
    s = (s or "").replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'").replace("\u2018", "'").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s.strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def mentions_one_of(final, names, variants=None):
    """Return the CANONICAL name (key) whose name or alias appears in the answer,
    or None when no name matches. `variants` maps a canonical name to extra
    alias tokens (e.g. ampersand-free forms)."""
    f = norm(final)
    for n in names:
        toks = [n]
        if variants and n in variants:
            toks += variants[n]
        for t in toks:
            if norm(t) in f:
                return n
    return None


def price_in(final, price, tol=0.51):
    """True when the answer mentions the given amount, accepting $ / USD /
    comma or period separators and a small tolerance (displayed prices are
    rounded on the page: 52.8 shows as $53)."""
    f = norm(final)
    p = float(price)
    for cand in ({p - tol, p, p + tol} if p != int(p) else {p}):
        whole = f"{cand:.2f}".rstrip("0").rstrip(".")
        for txt in (whole, f"{cand:.2f}", f"{cand:.0f}", whole.replace(".", ",")):
            if txt and txt in f:
                return True
    if abs(p - round(p)) < 1e-9:
        whole = str(int(round(p)))
        return bool(re.search(r"(?<![\d.])" + whole + r"(?![\d])", f))
    return False


def count_claim(final, number, words=("hotel", "propert", "result", "option", "left", "available", "match")):
    """True when the answer claims `number` as a count of one of the given
    word stems ('3 hotels', 'there are 3 properties', '3 left after ...')."""
    f = norm(final)
    n = str(number)
    for w in words:
        if re.search(rf"(?<![\d.]){n}(?![\d])[^.;]{{0,40}}{w}", f) or \
           re.search(rf"{w}[^.;]{{0,40}}(?<![\d.]){n}(?![\d])", f):
            return True
    return False


def first_mention(final, tokens):
    """Index (in the normalized answer) of the earliest occurrence among tokens,
    or None when none of them appears. Used for ordering-sensitive answers."""
    f = norm(final)
    idxs = [f.find(norm(t)) for t in tokens if f.find(norm(t)) >= 0]
    return min(idxs) if idxs else None


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
        return arg if Path(arg).exists() else None  # a bad explicit path FAILs the check, never crashes
    try:
        return fetch_db(container, kind)
    except Exception:
        return None  # caller FAILs the check that needs it


def run_local_db(run_dir, kind):
    """A run package may pin its own DB snapshots (run_task.sh records them):
    <run_dir>/initial.db (seed-state) and <run_dir>/after.db (after-state).
    Preferring these makes grading deterministic -- the verdict then depends only
    on what the run recorded, not on what the live container happens to hold at
    grading time (e.g. another task's mid-flight booking delta)."""
    if not run_dir:
        return ""
    p = Path(run_dir) / ("initial.db" if kind == "instance_seed" else "after.db")
    return str(p) if p.exists() else ""


def resolve_run_dbs(a, judge):
    """Resolve (initial, after) DB paths for a run: explicit args win, then the
    run package's own snapshots, then the live container fetch. The resolved
    paths are recorded as evidence so every verdict shows which DBs graded it."""
    init = a.initial_db or run_local_db(a.run_dir, "instance_seed")
    after = a.after_db or run_local_db(a.run_dir, "instance")
    if not init:
        init = resolve_db("", a.container, "instance_seed")
    if not after:
        after = resolve_db("", a.container, "instance")
    judge.check("dbs_resolved", bool(init and after),
                f"initial={'pinned' if (a.initial_db or run_local_db(a.run_dir, 'instance_seed')) else 'live'} "
                f"after={'pinned' if (a.after_db or run_local_db(a.run_dir, 'instance')) else 'live'}"
                f" (explicit --initial_db/--after_db > run-dir snapshots > live container)")
    return init, after


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _rows(db_path, table):
    con = sqlite3.connect(db_path)
    try:
        try:
            return con.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.Error:
            return []
    finally:
        con.close()


def db_fingerprint(db_path):
    """Content fingerprint of the benchmark tables: (rows, sha16) per table."""
    if not db_path:
        return None
    parts = []
    for t in TABLES:
        rows = _rows(db_path, t)
        blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
        parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
    return ";".join(parts)


def read_only_run(initial_db, after_db):
    """True when the after-state DB is row-for-row identical to the seed state.
    None when either DB is unavailable."""
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None
    return a == b


def _dates_match(check_in, check_out, expect_md):
    """True when (check_in, check_out) month-days equal expect_md == ('MM-DD', 'MM-DD')."""
    if not expect_md:
        return True
    try:
        ci = str(check_in)[:10] if check_in else ""
        co = str(check_out)[:10] if check_out else ""
        return (ci[5:10] == expect_md[0] and co[5:10] == expect_md[1])
    except Exception:
        return False


def booking_db_delta(initial_db, after_db, allowed_property_ids,
                     expect_md=None, check_fn=None):
    """Classify the DB delta of a BOOKING task (tasks 6 / 11 / 13 / 14).

    The task invites the agent to reserve/book a property from the allowed set
    with the task's dates. Accept exactly that and nothing else:
      * cart_item rows ADDED for an allowed property under the demo user (or a
        newly-registered user) with matching check-in/check-out month-days;
      * booking + booking_item rows ADDED for an allowed property (with the
        seeded cart items the checkout legitimately consumed);
      * cart_item rows REMOVED only when they belonged to the acting user and
        existed in the seed (bag cleanup / checkout consumption);
      * saved_property rows ADDED for an allowed property;
      * user rows ADDED (a fresh registration) with no changes/removals;
      * every other table must be identical.
    check_fn(cart_item_row) -> bool optionally validates extra row fields
    (adults/rooms). Returns (ok, detail, evidence_row) where evidence_row is
    the accepted cart/booking item when ok, else None.
    """
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable", None
    allowed = set(allowed_property_ids)
    violations, accepted = [], []

    seed_users = {r[0] for r in _rows(initial_db, "user")}
    after_users = {r[0] for r in _rows(after_db, "user")}
    # user: additions only
    if len(after_users) > len(seed_users) + 1:
        violations.append(f"user: {len(after_users) - len(seed_users)} rows added (at most 1 registration allowed)")

    before_cart = {repr(r): r for r in _rows(initial_db, "cart_item")}
    after_cart = {repr(r): r for r in _rows(after_db, "cart_item")}
    new_cart = [r for k, r in after_cart.items() if k not in before_cart]
    gone_cart = [r for k, r in before_cart.items() if k not in after_cart]

    before_book = {repr(r): r for r in _rows(initial_db, "booking")}
    after_book = {repr(r): r for r in _rows(after_db, "booking")}
    new_book = [r for k, r in after_book.items() if k not in before_book]
    gone_book = [r for k, r in before_book.items() if k not in after_book]
    if gone_book:
        violations.append(f"booking: {len(gone_book)} row(s) removed/changed")

    before_bi = {repr(r): r for r in _rows(initial_db, "booking_item")}
    after_bi = {repr(r): r for r in _rows(after_db, "booking_item")}
    new_bi = [r for k, r in after_bi.items() if k not in before_bi]
    gone_bi = [r for k, r in before_bi.items() if k not in after_bi]
    if gone_bi:
        violations.append(f"booking_item: {len(gone_bi)} row(s) removed/changed")

    # bookings belong to the acting user (demo or a fresh registration)
    new_user_ids = after_users - seed_users
    acting_ids = {DEMO_USER_ID} | new_user_ids
    for b in new_book:
        # booking columns: (id, user_id, confirmation, status, ...)
        if len(b) > 1 and b[1] not in acting_ids:
            violations.append(f"booking: added row for user_id={b[1]} (not the demo/registered user)")

    # booking items must reference allowed properties or cart rows the booking consumed
    consumed = {r[2] for r in gone_cart if len(r) > 2}
    ok_items, item_dates_ok = [], []
    for bi in new_bi:
        pid = bi[2] if len(bi) > 2 else None
        if pid in allowed or pid in consumed:
            ok_items.append(bi)
        else:
            violations.append(f"booking_item: added row for property_id={pid} (not an allowed property)")

    # cart adds must be for allowed properties with the task's dates
    for r in new_cart:
        pid = r[2] if len(r) > 2 else None
        uid = r[1] if len(r) > 1 else None
        if pid not in allowed:
            violations.append(f"cart_item: added row for property_id={pid} (not an allowed property for this task)")
        elif uid not in acting_ids:
            violations.append(f"cart_item: added row for user_id={uid} (not the demo/registered user)")
        elif not _dates_match(r[3], r[4], expect_md):
            violations.append(f"cart_item: dates {r[3]}..{r[4]} do not match the task's dates {expect_md}")
        elif check_fn and not check_fn(r):
            violations.append(f"cart_item: row fails the task's occupancy check: {r}")
        else:
            accepted.append(("cart_item", pid, r))

    # booking items for allowed properties with the task's dates
    for bi in ok_items:
        pid = bi[2] if len(bi) > 2 else None
        if pid in allowed:
            if not _dates_match(bi[3], bi[4], expect_md):
                violations.append(f"booking_item: dates {bi[3]}..{bi[4]} do not match the task's dates {expect_md}")
            else:
                accepted.append(("booking_item", pid, bi))

    # cart removals: only seed rows of the acting user
    for r in gone_cart:
        uid = r[1] if len(r) > 1 else None
        if uid not in acting_ids:
            violations.append(f"cart_item: removed a row of user_id={uid}")

    # saved_property: adds for allowed properties only
    before_sp = {repr(r) for r in _rows(initial_db, "saved_property")}
    after_sp = [r for k, r in {repr(r): r for r in _rows(after_db, "saved_property")}.items() if k not in before_sp]
    for r in after_sp:
        pid = r[2] if len(r) > 2 else None
        if pid not in allowed:
            violations.append(f"saved_property: added row for property_id={pid} (not an allowed property)")

    # every other table identical
    for t in TABLES:
        if t in ("user", "cart_item", "booking", "booking_item", "saved_property"):
            continue
        if _rows(initial_db, t) != _rows(after_db, t):
            violations.append(f"{t}: modified (no writes allowed)")

    if violations:
        return False, "; ".join(violations)[:300], None
    if not accepted:
        return False, "no cart/booking row for an allowed property with the task's dates", None
    kinds = sorted({a[0] for a in accepted})
    return True, f"db = seed + accepted {'/'.join(kinds)} for allowed property " \
                 f"{sorted({a[1] for a in accepted})} dates={expect_md}", accepted[0][2]


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
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-booking")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a):
    """Package gate + non-empty answer + strict read-only DB check shared by
    every non-booking task. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init, after = resolve_run_dbs(a, judge)
    ro = read_only_run(init, after)
    if ro is None:
        judge.check("db_state", False, "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ro, "instance DB identical to seed (read-only task)" if ro
                   else "instance DB differs from seed (read-only task)")
    return t, fa


def grade_booking(judge, a, allowed_property_ids, expect_md=None, check_fn=None):
    """Package gate + non-empty answer + booking-delta DB check for tasks
    6 / 11 / 13 / 14. Returns (traj, final_answer)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init, after = resolve_run_dbs(a, judge)
    ok, detail, row = booking_db_delta(init, after, allowed_property_ids,
                                       expect_md=expect_md, check_fn=check_fn)
    if ok is None:
        judge.check("db_state", False, "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa
