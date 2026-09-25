#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for MTA task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/megabus/verify/verify_lib.py``, ``sites/michaels/verify/verify_lib.py``).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the LIRR timetables, the railroad fare
     finder (with the task's exact station pair + ticket type), the elevator &
     escalator status search, the planned-service-changes browser (mode+window),
     the lost-and-found claim flow, the feedback form, the account area
     (OMNY/favorites/subscriptions/cases/AAR), the guides, the transparency and
     project/press pages, the tolls pages. A correct answer with no matching
     navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / time matching
     against frozen ground truth that is HARDCODED in each ``verify_N.py``
     (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require a row-identical database; stateful tasks require
     the exact allowed row delta and nothing else (one lost_claims row, one
     feedback_cases row, one aar_trips row, one users row with its favorites
     and alert_subscriptions, or the favorites/subscriptions set swap).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-mta-review)
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
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

SITE = "mta"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-mta-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("aar_trips", "alert_subscriptions", "content_pages", "equipment", "favorites",
          "feedback_cases", "lost_claims", "mnr_fares", "omny_taps", "outages",
          "port_jervis_fares", "press_releases", "projects", "rail_fares",
          "service_alerts", "stations", "stop_times", "subway_routes", "transfers",
          "trips", "users")
SEED_COUNTS = {"aar_trips": 3, "alert_subscriptions": 8, "content_pages": 253,
               "equipment": 707, "favorites": 12, "feedback_cases": 3, "lost_claims": 3,
               "mnr_fares": 249, "omny_taps": 33, "outages": 76, "port_jervis_fares": 100,
               "press_releases": 44, "projects": 19, "rail_fares": 576,
               "service_alerts": 391, "stations": 737, "stop_times": 1553677,
               "subway_routes": 26, "transfers": 75, "trips": 84656, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/mta.db.
SCHEMA_SHA256 = "186c9829b79061e6636e83cfc76b8eeb7e36455260defa00e4a1cf9b5db3f34f"
# sha256 over every row of the small/medium tables (ordered by the first two
# columns). Deterministic build-time seed (PYTHONHASHSEED=0).
SMALL_TABLES = ("aar_trips", "alert_subscriptions", "equipment", "favorites",
                "feedback_cases", "lost_claims", "mnr_fares", "omny_taps", "outages",
                "port_jervis_fares", "press_releases", "projects", "rail_fares",
                "service_alerts", "stations", "subway_routes", "transfers", "users")
SEED_ROWS_SHA256 = "8390cd94e510c94d49587a6939eb1475bcd8bfe6734050eb52a4039b3b0ceb9d"
# The two GTFS tables carry 1.6M rows; their fingerprint is count + id
# aggregates + the first/last 500 ordered rows (a surgical in-place edit that
# preserves all of those is not a realistic benchmark behavior).
BIG_TABLES = ("trips", "stop_times")
BIG_FP_SHA256 = "59a3732f088eb900cd76ba5a2d7db4f41e43319c44730604fd8f692d6ad6e127"

SEED_USERS = {  # email -> (username, display_name, omny_serial)
    "alice.j@test.com": ("alice_j", "Alice Johnson", "OMNY-4A21B9C3"),
    "bob.c@test.com": ("bob_c", "Bob Chen", "OMNY-77D0E5A2"),
    "carol.d@test.com": ("carol_d", "Carol Davis", "OMNY-9B33C1F7"),
    "david.k@test.com": ("david_k", "David Kim", "OMNY-2E54A8D0"),
}
DEMO_PASSWORD = "TestPass123!"

# Deterministic first-issued reference on the pinned day (2026-09-23) after a
# clean reset (3 seeded rows per category feed next_ref's row counter).
FIRST_CASE_REF = "CS-26095598"
FIRST_CLAIM_REF = "LF-26096491"
FIRST_AAR_REF = "AAR-26096609"

INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}


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


def navigated_fare_finder(traj, origin, dest, ticket):
    """/fares-tolls/lirr-metro-north/fare-finder visit with the exact pair+ticket."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/fares-tolls/lirr-metro-north/fare-finder":
            continue
        q = _query_params(u)
        if (origin in q.get("from", []) and dest in q.get("to", [])
                and ticket in q.get("ticket", [])):
            return True
        # a submit via GET without query on the URL (form posts are GET here) —
        # accept a bare finder visit only when paired with input evidence
    return False


def navigated_timetable(traj, path_prefix):
    return any(normalized_url_path(u).startswith(path_prefix) for u in site_urls(traj))


def navigated_planned_changes(traj, mode, when):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/planned-service-changes":
            continue
        q = _query_params(u)
        if mode in q.get("mode", []) and when in q.get("when", []):
            return True
    return False


def navigated_elevator_search(traj, station_sub):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/elevator-escalator-status":
            continue
        q = _query_params(u)
        if any(station_sub in v for v in q.get("station", [])):
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
def _answer_tokens(answer):
    return normalize_text(answer)


def contains_phrase(answer, phrase):
    return normalize_text(phrase) in _answer_tokens(answer)


def contains_any_phrase(answer, phrases):
    return any(contains_phrase(answer, p) for p in phrases)


def contains_amount(answer, amount, tolerance=0.011):
    """$13.50 / 13.50 / $13.5 — accepts optional $ and thousands separators."""
    text = _answer_tokens(answer)
    wanted = float(amount)
    for m in re.finditer(r"\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?", text):
        whole = m.group(1).replace(",", "")
        frac = m.group(2) or ""
        try:
            value = float(whole + ("." + frac if frac else ""))
        except ValueError:
            continue
        if abs(value - wanted) <= tolerance:
            return True
    return False


def contains_count(answer, n):
    text = _answer_tokens(answer)
    return re.search(rf"\b{n}\b", text) is not None


def contains_time(answer, hhmm, ampm=None):
    """8:20 / 08:20 / 8:20 a.m. — hour:minute must appear with the right clock."""
    text = _answer_tokens(answer)
    h, m = hhmm.split(":")
    h12 = str(int(h) % 12 or 12)
    patterns = [rf"{int(h):02d}:{m}", rf"{h12}:{m}"]
    if ampm:
        return any(re.search(p + rf"\s*(?:{ampm[0]}\.?m\.|{ampm})", text) for p in patterns)
    return any(re.search(p, text) for p in patterns)


def contains_ref(answer, ref):
    return ref.lower() in _answer_tokens(answer)


# ---------------------------------------------------------------- DB plumbing
def _connect(path):
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _docker_seed(container):
    out = Path(tempfile.mkdtemp(prefix="mta-verify-"))
    seed = out / "initial.db"
    subprocess.run(["docker", "cp", f"{container}:/opt/WebSyn/mta/instance_seed/mta.db", str(seed)],
                   check=True, capture_output=True, timeout=120)
    return seed


def _docker_live(container):
    out = Path(tempfile.mkdtemp(prefix="mta-verify-"))
    live = out / "after.db"
    subprocess.run(["docker", "cp", f"{container}:/opt/WebSyn/mta/instance/mta.db", str(live)],
                   check=True, capture_output=True, timeout=120)
    return live


def resolve_dbs(run_dir, initial_db, after_db, container):
    d = Path(run_dir)
    if initial_db is None:
        cand = d / "initial.db"
        initial_db = cand if cand.is_file() else _docker_seed(container)
    if after_db is None:
        cand = d / "after.db"
        after_db = cand if cand.is_file() else _docker_live(container)
    return Path(initial_db), Path(after_db)


def table_counts(db_path):
    con = _connect(db_path)
    try:
        out = {}
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out
    finally:
        con.close()


def schema_sha(db_path):
    con = _connect(db_path)
    try:
        h = hashlib.sha256()
        for r in con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master "
                              "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"):
            h.update(repr(r).encode())
        return h.hexdigest()
    finally:
        con.close()


def small_rows_sha(db_path):
    con = _connect(db_path)
    try:
        h = hashlib.sha256()
        for t in SMALL_TABLES:
            for r in con.execute(f"SELECT * FROM {t} ORDER BY 1, 2"):
                h.update(repr(r).encode())
        return h.hexdigest()
    finally:
        con.close()


def big_tables_fp(db_path):
    con = _connect(db_path)
    try:
        h = hashlib.sha256()
        for t in BIG_TABLES:
            n, s, mn, mx = con.execute(f"SELECT COUNT(*), SUM(id), MIN(id), MAX(id) FROM {t}").fetchone()
            h.update(f"{t}:{n}:{s}:{mn}:{mx};".encode())
            for r in con.execute(f"SELECT * FROM {t} ORDER BY id LIMIT 500"):
                h.update(repr(r).encode())
            for r in con.execute(f"SELECT * FROM {t} ORDER BY id DESC LIMIT 500"):
                h.update(repr(r).encode())
        return h.hexdigest()
    finally:
        con.close()


def check_seed_contract(judge, db_path, label="initial_db"):
    """The initial DB must be the frozen seed (schema + counts + rows)."""
    judge.check(f"{label}_schema", schema_sha(db_path) == SCHEMA_SHA256,
                f"schema sha {schema_sha(db_path)[:12]}… != {SCHEMA_SHA256[:12]}…")
    counts = table_counts(db_path)
    drift = {t: (counts.get(t), SEED_COUNTS[t]) for t in SEED_COUNTS
             if counts.get(t) != SEED_COUNTS[t]}
    judge.check(f"{label}_counts", not drift, f"count drift={drift}")
    judge.check(f"{label}_rows", small_rows_sha(db_path) == SEED_ROWS_SHA256,
                "small-table row hash mismatch")
    judge.check(f"{label}_big_tables", big_tables_fp(db_path) == BIG_FP_SHA256,
                "GTFS table fingerprint mismatch")


def check_read_only(judge, initial_db, after_db):
    """After-state must be row-identical to the initial state."""
    judge.check("read_only_counts", table_counts(after_db) == table_counts(initial_db),
                f"counts differ: {table_counts(after_db)} vs {table_counts(initial_db)}")
    judge.check("read_only_rows", small_rows_sha(after_db) == small_rows_sha(initial_db),
                "small-table rows differ")
    judge.check("read_only_big", big_tables_fp(after_db) == big_tables_fp(initial_db),
                "GTCS table fingerprint differs")


def rows_of(db_path, table, where="", args=()):
    con = _connect(db_path)
    try:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        q = f"SELECT * FROM {table} {where}"
        return [dict(zip(cols, r)) for r in con.execute(q, args)]
    finally:
        con.close()


def added_rows(after_db, initial_db, table, key):
    before = {r[key] for r in rows_of(initial_db, table)}
    return [r for r in rows_of(after_db, table) if r[key] not in before]


def removed_rows(after_db, initial_db, table, key):
    after = {r[key] for r in rows_of(after_db, table)}
    return [r for r in rows_of(initial_db, table) if r[key] not in after]


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    """No table outside ``allowed`` may change (counts then rows)."""
    ci, ca = table_counts(initial_db), table_counts(after_db)
    changed = {t for t in ci if ci[t] != ca.get(t)}
    unexpected = changed - set(allowed)
    judge.check("no_unexpected_table_count_change", not unexpected,
                f"unexpected count changes: {sorted(unexpected)}")
    for t in SMALL_TABLES:
        if t in unexpected:
            continue
        if t in allowed:
            continue
        if rows_of(initial_db, t) != rows_of(after_db, t):
            judge.check(f"table_{t}_unchanged", False, f"{t} rows changed without permission")


def user_by_email(db_path, email):
    for r in rows_of(db_path, "users"):
        if (r["email"] or "").lower() == email.lower():
            return r
    return None


def user_favorites(db_path, user_id):
    return sorted((r["service_type"], r["service_id"]) for r in rows_of(db_path, "favorites")
                  if r["user_id"] == user_id)


def user_subscriptions(db_path, user_id):
    return sorted((r["service_type"], r["service_id"]) for r in rows_of(db_path, "alert_subscriptions")
                  if r["user_id"] == user_id)


# ---------------------------------------------------------------- verdict plumbing
class Judge:
    def __init__(self):
        self.evidence = []
        self.failed = []

    def check(self, name, ok, detail=""):
        ok = bool(ok)
        self.evidence.append({"check": name, "ok": ok, "detail": str(detail)[:400]})
        if not ok:
            self.failed.append(name)

    @property
    def passed(self):
        return not self.failed


def _png_ok(path):
    try:
        head = Path(path).read_bytes()[:8]
    except OSError:
        return False
    return head == b"\x89PNG\r\n\x1a\n"


def check_trajectory_identity(judge, traj, task_id):
    judge.check("task_id", traj.get("task_id") == task_id,
                f"task_id={traj.get('task_id')!r}, expected {task_id!r}")
    judge.check("terminated_agent_done",
                bool(traj.get("terminated")) and traj.get("termination_reason") == "agent_done",
                f"terminated={traj.get('terminated')!r} reason={traj.get('termination_reason')!r}")
    answer = final_answer(traj)
    judge.check("final_answer_nonempty", len(answer) >= 10, f"answer len={len(answer)}")
    urls = trajectory_urls(traj)
    start = traj.get("start_url")
    judge.check("start_url_present", bool(start), "missing start_url")
    if start:
        p = urlparse(str(start))
        origin = (p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80))
        bad = []
        for u in urls:
            q = urlparse(str(u))
            if not is_site_url(u):
                bad.append(u)
                continue
            if (q.scheme, q.hostname, q.port or (443 if q.scheme == "https" else 80)) != origin:
                bad.append(u)
        judge.check("same_origin_urls", not bad, f"off-origin urls: {bad[:3]}")
    shots = traj.get("_shots") or {}
    judge.check("screenshots_present", len(shots) >= 1, f"shots={len(shots)}")
    bad_shots = [n for n, p in list(shots.items())[:50] if not _png_ok(p)]
    judge.check("screenshots_decode_png", not bad_shots, f"bad: {bad_shots[:3]}")


def check_visited_path(judge, traj, name, path):
    judge.check(name, navigated_to_path(traj, path), f"required: {path}")


def run_verifier(task_id, run_checks):
    ap = sys.argv
    args = {"--run_dir": None, "--initial_db": None, "--after_db": None, "--container": None}
    i = 1
    while i < len(ap):
        if ap[i] in args:
            args[ap[i]] = ap[i + 1]
            i += 2
        else:
            i += 1
    if not args["--run_dir"]:
        print(json.dumps({"task_id": task_id, "pass": False,
                          "reason": "usage: verify_N.py --run_dir DIR [--initial_db P] [--after_db P] [--container NAME]"}))
        sys.exit(2)
    container = args["--container"] or DEFAULT_CONTAINER
    judge = Judge()
    try:
        traj = load_run(args["--run_dir"])
        initial_db, after_db = resolve_dbs(args["--run_dir"], args["--initial_db"],
                                           args["--after_db"], container)
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — fail closed on any infra error
        print(json.dumps({"task_id": task_id, "pass": False,
                          "reason": f"infra_error: {type(exc).__name__}: {exc}",
                          "evidence": judge.evidence}))
        sys.exit(1)
    verdict = {"task_id": task_id, "pass": judge.passed,
               "reason": "all checks passed" if judge.passed else "failed: " + ", ".join(judge.failed),
               "evidence": judge.evidence}
    print(json.dumps(verdict))
    sys.exit(0 if judge.passed else 1)
