#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for NFL task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/megabus/verify/verify_lib.py``, ``sites/michaels/verify/verify_lib.py``).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the stats leaderboards, player pages,
     team pages / rosters / schedules, scores weeks and game centers, standings,
     the newsroom and article pages, the video hub and channels, the injury
     report, the transactions log, the NFL+ plans page and the checkout chain,
     the account area, and the site search. A correct answer with no matching
     navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / record /
     date matching against frozen ground truth that is HARDCODED in each
     ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require every table row-identical; stateful tasks require
     the exact allowed row delta and nothing else (a created user + subscription
     + order, a plan switch with the old subscription cancelled, a favourite
     team update, a subscription cancellation, a newsletter signup row).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-nfl-review)
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
from urllib.parse import unquote, urlparse

SITE = "nfl"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-nfl-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("games", "injuries", "news", "newsletter_signups", "players", "plus_orders",
          "stat_leaders", "subscriptions", "teams", "transactions", "users", "videos")
SEED_COUNTS = {"games": 272, "injuries": 259, "news": 82, "newsletter_signups": 0,
               "players": 2538, "plus_orders": 2, "stat_leaders": 275,
               "subscriptions": 3, "teams": 32, "transactions": 86, "users": 4,
               "videos": 280}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/nfl.db.
SCHEMA_SHA256 = "4769463c1038e30e5fbd3c192f005b662be9e0381f5befab87362933aa051872"
# sha256 over every seed row (table-canonical, ORDER BY all columns). The seed is
# built deterministically at image build time (PYTHONHASHSEED=0) and a clean
# in-container rebuild reproduces it byte-for-byte.
SEED_ROWS_SHA256 = "e064b333f86227b63dc7940bdca32e157fdd7347aa2cea2fd06663eaa67ab398"
SEED_USERS = {  # email -> (id, display name); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson"),
    "bob.c@test.com": (2, "Bob Chen"),
    "carol.d@test.com": (3, "Carol Davis"),
    "david.k@test.com": (4, "David Kim"),
}
DEMO_PASSWORD = "TestPass123!"
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}
MIRROR_DATE = "2026-09-24"  # frozen snapshot date (app.MIRROR_DATE)
TAX_RATE = 0.0895           # checkout tax constant (app.plus_subscribe)


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


def navigated_to(traj, substr, times=1):
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def navigated_query_url(traj, path, **params):
    """/search visit whose query string contains each expected param value."""
    expected_items = sorted((k, unquote(str(v))) for k, v in params.items())
    for u in site_urls(traj):
        if normalized_url_path(u) != normalized_url_path(path):
            continue
        query = urlparse(u).query
        got = []
        for pair in query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                got.append((k, unquote(v)))
        if all(item in got for item in expected_items):
            return True
    return False


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
    """A money value like 108.94 (optionally prefixed with $) appears in the answer."""
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
    """The integer count appears as a standalone number (not part of money/decimal)."""
    for m in re.finditer(r"(?<![\d.,\$])\d+(?![\d.,])", str(answer)):
        if int(m.group(0)) == int(count):
            return True
    return False


def contains_time(answer, hhmm):
    """A kickoff time matches in either 24h (20:15) or US (8:15pm) style."""
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


def contains_record(answer, wins, losses, ties=0):
    """A W-L(-T) record like 2-0 appears (dashes of any kind)."""
    a = normalize_text(answer)
    if ties:
        return re.search(rf"\b{wins}\s*-\s*{losses}\s*-\s*{ties}\b", a) is not None
    return re.search(rf"\b{wins}\s*-\s*{losses}(?!\s*-\s*\d)", a) is not None


def contains_date(answer, iso_date):
    """A date like 2026-10-24 appears in any of: ISO, 'Oct 24, 2026', 'October 24,
    2026', '10/24/2026', 'Oct. 24'."""
    from datetime import date
    d = date.fromisoformat(iso_date)
    a = normalize_text(answer)
    forms = [iso_date, iso_date.replace("-", "/"),
             f"{d.strftime('%b')} {d.day}, {d.year}".lower(),
             f"{d.strftime('%B')} {d.day}, {d.year}".lower(),
             f"{d.strftime('%b')} {d.day}".lower(),
             f"{d.strftime('%B')} {d.day}".lower(),
             f"{d.month}/{d.day}/{d.year}"]
    return any(f in a for f in forms)


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
    # Always fetch a fresh copy: grading multiple runs in sequence must never
    # reuse a stale snapshot (the DB changes between resets).
    cache = Path(tempfile.gettempdir()) / f"{SITE}_verify_{which}.db"
    cache.unlink(missing_ok=True)
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
        raise ValueError("initial_db is not the frozen nfl seed (rows sha mismatch)")
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
                    "both initial (seed) and after (instance) nfl database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- nfl-specific helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return rows[0] if rows else None


def active_subscription(db_path, user_id):
    rows = db_query(db_path, "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' "
                             "ORDER BY id DESC", (user_id,))
    return rows[0] if rows else None


def subscriptions_of(db_path, user_id):
    return db_query(db_path, "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id", (user_id,))


def orders_of(db_path, user_id):
    return db_query(db_path, "SELECT * FROM plus_orders WHERE user_id = ? ORDER BY id", (user_id,))


def added_rows(after_db, initial_db, table, key):
    init = {str(r[key]) for r in db_query(initial_db, f"SELECT {key} FROM {table}")}
    return [r for r in db_query(after_db, f"SELECT * FROM {table} ORDER BY id")
            if str(r[key]) not in init]


def newsletter_rows(db_path):
    return db_query(db_path, "SELECT * FROM newsletter_signups ORDER BY id")


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    changed = changed_tables(initial_db, after_db)
    extra = [t for t in changed if t not in set(allowed)]
    judge.check("db_only_expected_tables_changed", not extra,
                f"changed={changed!r}, allowed={sorted(set(allowed))!r}")


def _table_rows_by_key(db_path, table, key):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return {str(r[key]): tuple(r) for r in con.execute(f'SELECT * FROM "{table}"')}
    finally:
        con.close()


def check_precise_delta(judge, initial_db, after_db, table, key,
                        changed_keys=(), added_keys=None):
    """Per-row delta gate: within `table`, ONLY the expected rows (by `key`)
    may change and only the expected new rows may appear. Any mutation of an
    unrelated row inside an otherwise-allowed table FAILs."""
    before = _table_rows_by_key(initial_db, table, key)
    after = _table_rows_by_key(after_db, table, key)
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    added = sorted(k for k in after if k not in before)
    removed = sorted(k for k in before if k not in after)
    ok = (changed == sorted(str(k) for k in changed_keys)
          and removed == []
          and (added_keys is None or added == sorted(str(k) for k in added_keys)))
    judge.check(f"db_{table}_precise_delta", ok,
                f"changed={changed!r} (expected {sorted(str(k) for k in changed_keys)!r}), "
                f"added={added!r}, removed={removed!r}")


def check_read_only_db(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    judge.check("db_read_only", changed == [],
                f"no table may change on a read-only task; changed={changed!r}")


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
            if not name:
                continue
            path = root / "screenshots" / Path(str(name)).name
            if not path.is_file():
                return False, f"step {index}: screenshot {name} is missing"
            if not _png_decodes(path):
                return False, f"step {index}: screenshot {name} is not a decodable PNG"
            checked += 1
    if not checked:
        return False, "no step screenshots recorded"
    return True, f"{checked} step screenshots decode"


def check_trajectory_identity(judge, traj, task_id):
    judge.check("task_id_matches", traj.get("task_id") == task_id,
                f"trajectory task_id={traj.get('task_id')!r}")
    terminated = bool(traj.get("terminated")) and traj.get("termination_reason") == "agent_done"
    judge.check("terminated_agent_done", terminated,
                f"terminated={traj.get('terminated')!r}, reason={traj.get('termination_reason')!r}")
    answer = final_answer(traj)
    judge.check("final_answer_nonempty", len(answer) > 0, f"answer length={len(answer)}")
    start_url = traj.get("start_url")
    recorded = trajectory_urls(traj)
    judge.check("all_urls_match_local_origin",
                bool(start_url) and bool(recorded)
                and all(_same_local_origin(u, start_url) for u in recorded),
                f"start_url={start_url!r}, recorded_urls={recorded[:6]!r}{'…' if len(recorded) > 6 else ''}")
    ok, detail = screenshots_decode(traj)
    judge.check("screenshots_decode", ok, detail)


def check_visited_path(judge, traj, name, path):
    judge.check(name, navigated_to_path(traj, path), f"required: {path}")


def check_visited_path_any(judge, traj, name, paths):
    judge.check(name, navigated_to_path_any(traj, paths), f"required any of: {paths}")
