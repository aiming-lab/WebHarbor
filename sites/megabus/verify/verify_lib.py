#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for Megabus task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/michaels/verify/verify_lib.py``, ``sites/instructure/verify/verify_lib.py``).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the home journey planner, journey results
     (with the task's originId/destinationId/departureDate), the fare finder,
     route guides / city guides / stops / help topics, the basket + checkout
     chain + confirmation, manage-booking (lookup / change / cancel), the
     account area, the tracker, service alerts, site search. A correct answer
     with no matching navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / time matching
     against frozen ground truth that is HARDCODED in each ``verify_N.py``
     (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require every table row-identical; stateful tasks require
     the exact allowed row delta and nothing else (an added booking row with
     its journeys / SMS flag / total, a basket row, a created user row, a
     profile update, a status flip to cancelled, a booking_journeys change).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-megabus-audit)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import hashlib
import ipaddress
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
from urllib.parse import parse_qs, unquote, urlparse

SITE = "megabus"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-megabus-audit")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("basket_items", "booking_journeys", "bookings", "bus_statuses", "cities",
          "city_guides", "contact_messages", "faq_entries", "journey_legs", "journeys",
          "newsletter_signups", "promo_codes", "route_guides", "saved_passengers",
          "service_alerts", "static_pages", "stops", "travel_dates", "users")
SEED_COUNTS = {"basket_items": 0, "booking_journeys": 8, "bookings": 8, "bus_statuses": 1,
               "cities": 753, "city_guides": 29, "contact_messages": 0, "faq_entries": 72,
               "journey_legs": 7630, "journeys": 6380, "newsletter_signups": 0,
               "promo_codes": 1, "route_guides": 575, "saved_passengers": 5,
               "service_alerts": 2, "static_pages": 9, "stops": 972,
               "travel_dates": 11846, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/megabus.db.
SCHEMA_SHA256 = "5f1ed73edf701982641486d0c36153059f6775a0920491773a4eccc4dc60ec20"
# sha256 over every seed row (table-canonical, ORDER BY all columns). The seed is
# built deterministically at image build time (PYTHONHASHSEED=0) and a clean
# in-container rebuild reproduces it byte-for-byte. Updated at audit stage:
# the closure capture of every upstream guide within two hops of the
# /route-guides index (517 additional pages, resolving all dead related-route
# links) grew route_guides 10 -> 575 and changed the rows digest.
SEED_ROWS_SHA256 = "8ed1a04fc31a76530e7211fe16f63e819be92cc369cd5659b6655d926bdfca10"
SEED_USERS = {  # email -> (id, name); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson"),
    "bob.c@test.com": (2, "Bob Chen"),
    "carol.d@test.com": (3, "Carol Davis"),
    "david.k@test.com": (4, "David Kim"),
}
DEMO_PASSWORD = "TestPass123!"
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}
BOOKING_FEE = 3.99
AMENDMENT_FEE = 7.50
SMS_FEE = 0.25
PROMO_EMAIL5 = ("EMAIL5", 5.00, 15.00)  # code, amount, min spend


# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(traj, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))} if shots_dir.is_dir() else {}
    return traj


def trajectory_urls(traj):
    urls = []
    if traj.get("start_url"):
        urls.append(str(traj["start_url"]))
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            if step.get(key):
                urls.append(str(step[key]))
    if traj.get("final_url"):
        urls.append(str(traj["final_url"]))
    return urls


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def is_site_url(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def site_urls(traj):
    return [u for u in trajectory_urls(traj) if is_site_url(u)]


def normalized_url_path(url):
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def _query_params(url):
    return {k: [unquote(v) for v in vals] for k, vals in
            parse_qs(urlparse(url).query, keep_blank_values=True).items()}


def navigated_to(traj, substr, times=1):
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def navigated_journeys(traj, origin_id, dest_id, date):
    """/journey-planner/journeys visit with exactly the task's route + date."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/journey-planner/journeys":
            continue
        q = _query_params(u)
        if (str(origin_id) in q.get("originId", []) and str(dest_id) in q.get("destinationId", [])
                and date in q.get("departureDate", [])):
            return True
    return False


def navigated_confirmation(traj):
    return any(normalized_url_path(u).startswith("/journey-planner/confirmation/")
               for u in site_urls(traj))


def entered_identity(traj, expected):
    """The expected string appears in an input step (case-insensitive)."""
    wanted = normalize_text(expected)
    for step in traj.get("steps") or []:
        if not isinstance(step, dict) or step.get("action") not in INPUT_ACTIONS:
            continue
        params = step.get("params") or {}
        for v in (params.get("text"), params.get("value")):
            if v is not None and wanted in normalize_text(str(v)):
                return True
    return False


def input_texts(traj):
    out = []
    for step in traj.get("steps") or []:
        if isinstance(step, dict) and step.get("action") in INPUT_ACTIONS:
            params = step.get("params") or {}
            for v in (params.get("text"), params.get("value")):
                if v is not None:
                    out.append(str(v))
    return out


def normalize_text(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-").replace("−", "-"))
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------- answer matching
def contains_all(answer, tokens):
    a = normalize_text(answer)
    return all(normalize_text(t) in a for t in tokens)


def contains_any(answer, tokens):
    a = normalize_text(answer)
    return any(normalize_text(t) in a for t in tokens)


def contains_phrase(answer, phrase):
    return normalize_text(phrase) in normalize_text(answer)


def contains_amount(answer, amount, tolerance=0.011):
    """A money value like 86.97 (optionally prefixed with $) appears in the answer."""
    wanted = float(amount)
    for m in re.finditer(r"\$?\s*(\d+(?:[.,]\d+)?)", str(answer)):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if abs(value - wanted) <= tolerance:
            return True
    return False


def contains_count(answer, count):
    """The integer count appears as a standalone number (not as part of a money/decimal)."""
    for m in re.finditer(r"(?<![\d.,\$])\d+(?![\d.,])", str(answer)):
        if int(m.group(0)) == int(count):
            return True
    return False


def contains_time(answer, hhmm):
    """A departure/arrival time matches in either 24h (08:35) or US (8:35am) style."""
    h, mm = hhmm.split(":")
    h24 = int(h)
    variants = {f"{h24}:{mm}", f"{h24:02d}:{mm}"}
    if h24 == 0:
        variants |= {f"12:{mm}am", f"12:{mm} am"}
    elif h24 < 12:
        variants |= {f"{h24}:{mm}am", f"{h24}:{mm} am", f"{h24:02d}:{mm}am"}
    elif h24 == 12:
        variants |= {f"12:{mm}pm", f"12:{mm} pm"}
    else:
        variants |= {f"{h24 - 12}:{mm}pm", f"{h24 - 12}:{mm} pm", f"{h24 - 12:02d}:{mm}pm"}
    a = normalize_text(answer).replace(" ", "")
    for v in variants:
        if v.replace(" ", "") in a:
            return True
    return False


def contains_duration(answer, minutes):
    """A duration in minutes appears as XhYm (e.g. 4h20m / 4 hours 20 minutes)."""
    h, m = divmod(int(minutes), 60)
    patterns = []
    if m == 0:
        patterns += [rf"{h}\s*(?:h|hours?|hr|hrs)\b", rf"{h}\s*:\s*00\b"]
    else:
        patterns += [rf"{h}\s*(?:h|hours?|hr|hrs)\s*{m:02d}\s*(?:m|minutes?|min)\b",
                     rf"{h}\s*(?:h|hours?|hr|hrs)\s*{m}\s*(?:m|minutes?|min)\b",
                     rf"{h}[:.]\s*{m:02d}"]
    a = normalize_text(answer)
    return any(re.search(p, a) for p in patterns)


# ---------------------------------------------------------------- snapshots
def db_query(db_path, sql, params=()):
    con = sqlite3.connect(str(db_path))
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def resolve_db(path, container, which):
    if path:
        p = Path(path)
        return p if p.is_file() else None
    cache = Path(tempfile.gettempdir()) / f"{SITE}_verify_{which}.db"
    if cache.is_file():
        return cache
    try:
        subprocess.run(["docker", "cp",
                        f"{container}:/opt/WebSyn/{SITE}/{which}/{SITE}.db", str(cache)],
                       check=True, capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    return cache if cache.is_file() else None


def schema_sha(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master "
                           "ORDER BY type, name").fetchall()
        h = hashlib.sha256()
        for r in rows:
            h.update(repr(tuple(r)).encode())
        return h.hexdigest()
    finally:
        con.close()


def rows_sha(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        h = hashlib.sha256()
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in names:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            order = ", ".join(f'"{c}"' for c in cols)
            for row in con.execute(f'SELECT * FROM "{t}" ORDER BY {order}'):
                h.update(repr(tuple(row)).encode())
        return h.hexdigest()
    finally:
        con.close()


def table_counts(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        out = {}
        for t in TABLES:
            out[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        return out
    finally:
        con.close()


def validate_snapshot_contract(initial_db, after_db):
    if schema_sha(initial_db) != SCHEMA_SHA256:
        raise ValueError(f"initial_db schema sha mismatch: {schema_sha(initial_db)}")
    counts = table_counts(initial_db)
    if counts != SEED_COUNTS:
        raise ValueError(f"initial_db table counts mismatch: {counts!r}")
    if rows_sha(initial_db) != SEED_ROWS_SHA256:
        raise ValueError("initial_db is not the frozen megabus seed (rows sha mismatch)")
    if schema_sha(after_db) != SCHEMA_SHA256:
        raise ValueError(f"after_db schema sha mismatch: {schema_sha(after_db)}")


def changed_tables(initial_db, after_db, tables=None):
    con_i = sqlite3.connect(str(initial_db))
    con_a = sqlite3.connect(str(after_db))
    try:
        names = tuple(tables) if tables else TABLES
        changed = []
        for t in names:
            cols = [r[1] for r in con_i.execute(f'PRAGMA table_info("{t}")')]
            order = ", ".join(f'"{c}"' for c in cols) or "1"
            ri = con_i.execute(f'SELECT * FROM "{t}" ORDER BY {order}').fetchall()
            ra = con_a.execute(f'SELECT * FROM "{t}" ORDER BY {order}').fetchall()
            if ri != ra:
                changed.append(t)
        return changed
    finally:
        con_i.close()
        con_a.close()


def resolve_snapshots(args, task_id):
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) megabus database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- megabus-specific helpers
def booking_by_reference(db_path, ref):
    rows = db_query(db_path, "SELECT * FROM bookings WHERE reference = ? LIMIT 1", (ref,))
    return rows[0] if rows else None


def booking_journeys_of(db_path, booking_id):
    return db_query(db_path, "SELECT * FROM booking_journeys WHERE booking_id = ? ORDER BY id",
                    (booking_id,))


def journey_of(db_path, journey_id):
    rows = db_query(db_path, "SELECT * FROM journeys WHERE id = ? LIMIT 1", (journey_id,))
    return rows[0] if rows else None


def added_bookings(after_db, initial_db):
    """New booking rows (by reference) present in after but not in initial."""
    init = {r["reference"] for r in db_query(initial_db, "SELECT reference FROM bookings")}
    added = []
    for r in db_query(after_db, "SELECT * FROM bookings ORDER BY id"):
        if r["reference"] not in init:
            added.append(r)
    return added


def added_users(after_db, initial_db):
    init = {r["email"] for r in db_query(initial_db, "SELECT email FROM users")}
    added = []
    for r in db_query(after_db, "SELECT * FROM users ORDER BY id"):
        if r["email"] not in init:
            added.append(r)
    return added


def basket_rows(db_path):
    return db_query(db_path, "SELECT * FROM basket_items ORDER BY id")


def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return rows[0] if rows else None


# ---------------------------------------------------------------- judge + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        self.task_id = task_id
        self.no_llm = bool(no_llm)
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence=""):
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def note(self, name, text):
        self.evidence.append(f"[INFO] {name}: {text}")

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason or "all checks passed",
                          "evidence": self.evidence}, ensure_ascii=False, indent=2))
        sys.exit(0 if self.ok else 1)


def fail_closed(task_id, reason, detail):
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    sys.exit(1)


@dataclass
class VerifyArgs:
    run_dir: str = ""
    initial_db: str = ""
    after_db: str = ""
    container: str = ""
    no_llm: str = "False"

    def post_process(self):
        if not self.container:
            self.container = DEFAULT_CONTAINER
        if self.run_dir:
            run = Path(self.run_dir)
            if not self.initial_db and (run / "initial.db").is_file():
                self.initial_db = str(run / "initial.db")
            if not self.after_db and (run / "after.db").is_file():
                self.after_db = str(run / "after.db")


def parse_args():
    try:
        import simpleArgParser as sap  # the agent_demo env; boolean flags take a value
    except ImportError:  # plain python3 fallback with the same flags
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--run_dir", required=True)
        parser.add_argument("--initial_db", default="")
        parser.add_argument("--after_db", default="")
        parser.add_argument("--container", default=DEFAULT_CONTAINER)
        parser.add_argument("--no_llm", nargs="?", const="True", default="False")
        ns = parser.parse_args()
        args = VerifyArgs(ns.run_dir, ns.initial_db, ns.after_db, ns.container,
                          str(ns.no_llm).strip().lower() in {"1", "true", "yes"})
        args.post_process()
        return args
    return sap.parse_args(VerifyArgs)


def run_verifier(task_id, run_checks):
    """Standard main(): load the run, resolve + validate snapshots, run the task
    checks, fail closed on error."""
    args = parse_args()
    try:
        traj = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(task_id, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, task_id)
    judge = Judge(task_id, no_llm=args.no_llm)
    try:
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


# ---------------------------------------------------------------- shared checks
def _same_local_origin(url, start_url):
    try:
        observed, start = urlparse(str(url or "")), urlparse(str(start_url or ""))
        return (observed.scheme == start.scheme == "http"
                and observed.hostname is not None and start.hostname is not None
                and not observed.username and not observed.password
                and observed.port == start.port
                and observed.hostname.casefold() == start.hostname.casefold()
                and is_site_url(url))
    except ValueError:
        return False


def _png_decodes(path):
    try:
        from PIL import Image  # available in the agent_demo env
    except ImportError:  # pragma: no cover - fallback when Pillow is absent
        data = Path(path).read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 33 or data[12:16] != b"IHDR":
            return False
        return int.from_bytes(data[16:20], "big") > 0 and int.from_bytes(data[20:24], "big") > 0
    try:
        with Image.open(path) as image:
            image.load()
            return image.format == "PNG" and image.width >= 1 and image.height >= 1
    except Exception:  # noqa: BLE001
        return False


def screenshots_decode(traj):
    root = Path(traj.get("_run_dir") or "")
    steps = traj.get("steps")
    if not root.is_dir() or not isinstance(steps, list) or not steps:
        return False, "run directory or steps are missing"
    checked = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step {index} is not an object"
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            rel = Path(str(name or ""))
            if not name or rel.is_absolute() or ".." in rel.parts:
                return False, f"step {index} has unsafe {key}"
            path = next((p for p in (root / "screenshots" / rel, root / rel) if p.is_file()), None)
            if path is None:
                return False, f"step {index} is missing {key}={name!r}"
            if not _png_decodes(path):
                return False, f"step {index} {key} is not a decodable non-empty PNG"
        checked += 1
    return True, f"decoded {checked} PNG screenshots"


def check_trajectory_identity(judge, traj, task_id, require_answer=True):
    answer = final_answer(traj)
    if require_answer:
        judge.check("final_answer_nonempty", bool(answer), f"final_answer={answer!r}")
    judge.check("trajectory_task_matches", str(traj.get("task_id") or "").strip() == task_id,
                f"expected_task_id={task_id!r}, observed_task_id={traj.get('task_id')!r}")
    judge.check("trajectory_completed",
                traj.get("terminated") is True and traj.get("termination_reason") == "agent_done",
                f"terminated={traj.get('terminated')!r}, reason={traj.get('termination_reason')!r}")
    steps = traj.get("steps")
    judge.check("trajectory_has_steps", isinstance(steps, list) and bool(steps),
                f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    recorded = trajectory_urls(traj)
    judge.check("all_urls_match_local_origin",
                bool(recorded) and all(_same_local_origin(u, traj.get("start_url", "")) for u in recorded),
                f"start_url={traj.get('start_url')!r}, recorded_urls={recorded!r}")
    ok, evidence = screenshots_decode(traj)
    judge.check("screenshots_decode", ok, evidence)


def check_signed_in_as(judge, traj, email):
    judge.check("visited_signin_page", navigated_to_path(traj, "/account-management/login"),
                "required_path=/account-management/login")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email),
                f"expected {email!r} in an input step; observed_inputs={input_texts(traj)!r}")


def check_visited_path(judge, traj, name, path):
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_read_only(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    return judge.check("read_only_db_unchanged", not changed, f"changed_tables={changed!r}")


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    check_precise_delta(judge, initial_db, after_db, allowed)
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


def check_precise_delta(judge, initial_db, after_db, allowed):
    """Preserve existing rows/cells even inside tables touched by a task."""
    task = int(judge.task_id.rsplit('--', 1)[1])
    for table in allowed:
        before = {r['id']: dict(r) for r in db_query(initial_db, f'SELECT * FROM {table}')}
        after = {r['id']: dict(r) for r in db_query(after_db, f'SELECT * FROM {table}')}
        for key, row in before.items():
            fields = set()
            if task == 3 and table == 'bookings' and row.get('reference') == 'M2V6YH': fields = {'total'}
            if task == 3 and table == 'booking_journeys' and row.get('booking_id') == 4: fields = {'journey_id', 'price'}
            if task == 4 and table == 'bookings' and row.get('reference') == 'W9C4FJ': fields = {'status'}
            if task == 17 and table == 'users' and row.get('email') == 'carol.d@test.com': fields = {'last_name', 'phone'}
            judge.check(f'preserve_{table}_{key}', key in after and all(after[key].get(k)==v for k,v in row.items() if k not in fields), 'Only requested fields of the target record may change')
        added = set(after)-set(before)
        expected = 1 if ((task in (0,2,19) and table in ('bookings','booking_journeys')) or (task==2 and table=='users') or (task==18 and table=='basket_items')) else 0
        judge.check(f'exact_added_{table}', len(added)==expected, f'expected {expected} added rows, found {len(added)}')
