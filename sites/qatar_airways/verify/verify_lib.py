#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for the qatar_airways
grading contract (authored by the reviewer on orch/review/qatar_airways).

DETERMINISTIC FIRST — no LLM call is load-bearing. Every check is reproducible
from the run signature (trajectory + screenshots + initial/after SQLite
snapshots), mirroring the hardened sibling suites
(``sites/porsche/verify/verify_lib.py``, ``sites/raising_canes/verify/verify_lib.py``)
with the qatar-specific gates:

  1. Package identity — task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin
     AND port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Seed identity — the run's initial DB must BE the frozen seed (schema
     digest + per-table row digest + row counts). A run that started from a
     mutated database fails closed: its "delta" is meaningless.
  3. Navigation gates (anti knowledge-shortcut) — the agent must have opened
     the on-site surfaces the task names: flight search with the task's
     route/cabin/passenger parameters, the booking chain (passenger details →
     payment → confirmation), Manage booking for the task PNR, check-in +
     boarding pass, flight-status queries, destination guides, the offer
     pages, the Privilege Club surfaces (login/join/dashboard/profile/
     calculator/tiers), fleet, baggage and help. A correct answer without
     matching navigation is a memory-recall shortcut = FAIL.
  4. Answer checks — affirmative token / phrase / amount / time matching
     against ground truth HARDCODED in each ``verify_N.py`` (never in
     tasks.jsonl). Negated mentions ("not 15:05") do not count.
  5. DB after-state — read-only tasks require all tables row-identical;
     stateful tasks require the exact allowed delta (one booking with its
     legs/passengers at the frozen route/date/fare/total; a status flip to
     cancelled; an extra-bag bump; seat assignments + a checked-in flag; an
     Avios debit + activity row; a profile update; a new member row) and
     every other table row-identical.

Runtime-random values (PNRs, membership numbers, ticket numbers) are matched
structurally: the value must appear verbatim in the agent's final answer AND
identify the added/changed row — never a hardcoded constant.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db,
                       else instance_seed from the container)
  --after_db PATH      after-state SQLite DB (default: <run_dir>/after.db,
                       else the live instance DB from the container)
  --container NAME     docker container to fetch DBs from (default $WH_CONTAINER
                       or wh-qa-review)
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 on PASS,
1 on FAIL. Any infrastructure error fails closed (infra_error: true).
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

SITE = "qatar_airways"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-qa-review")

# ---------------------------------------------------------------- frozen seed contract
# Derived by the reviewer from the independently built in-image seed
# (webharbor:qa-review, Docker build step 89/90; seed sha256
# 602979203eddb57a8391dae603282aef1b86d03b7f6cea3dc257e93f2b5e0478).
TABLES = ("activities", "aircraft", "airports", "booking_legs", "bookings",
          "destinations", "faqs", "flight_statuses", "flights", "offers",
          "passengers", "subscriptions", "users")
SEED_COUNTS = {"activities": 14, "aircraft": 10, "airports": 2518,
               "booking_legs": 9, "bookings": 7, "destinations": 253,
               "faqs": 41, "flight_statuses": 511, "flights": 500,
               "offers": 10, "passengers": 9, "subscriptions": 0, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of the frozen seed.
SEED_SCHEMA_SHA256 = "578f2661decd74a1d81fa2a88d3c6832add7e6915048712a1f16f7d07c69ea16"
# sha256 over every row of every table (table, {col: val}) in table order.
SEED_ROWS_SHA256 = "49c190978c4345bb36e1f4e28ef36c8ebac94ee550527b854be69c809f649b25"

SEED_USERS = {
    "alice.j@test.com": ("Alice", "Johnson", "Gold", "QRPC0004217"),
    "bob.c@test.com": ("Bob", "Chen", "Silver", "QRPC0007752"),
    "carol.d@test.com": ("Carol", "Davis", "Burgundy", "QRPC0009134"),
    "david.k@test.com": ("David", "Kim", "Platinum", "QRPC0001588"),
}
DEMO_PASSWORD = "TestPass123!"
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}
PNR_RE = re.compile(r"\b[A-Z0-9]{6}\b")
PNR_STOPWORDS = {"ECONOMY", "BUSINESS", "QATAR", "AIRWAYS", "FIRST", "CLASS"}


# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(traj, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    traj["_run_dir"] = d
    shots_dir = d / "screenshots"
    traj["_shots"] = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))} \
        if shots_dir.is_dir() else {}
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
            parse_qs(urlparse(str(url)).query, keep_blank_values=True).items()}


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def pnr_tokens(answer):
    return {p for p in PNR_RE.findall(answer or "") if p.upper() not in PNR_STOPWORDS}


# ---------------------------------------------------------------- navigation gates
def navigated_search(traj, origin=None, dest=None, cabin=None, promo=None,
                     adults=None):
    """/en/search-results.html visit whose query carries route/cabin/promo/pax."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/en/search-results.html":
            continue
        q = _query_params(u)
        if origin and origin.upper() not in [v.upper() for v in q.get("from", [])]:
            continue
        if dest and dest.upper() not in [v.upper() for v in q.get("to", [])]:
            continue
        if cabin and cabin.lower() not in [v.lower() for v in q.get("cabin", [])]:
            continue
        if promo and promo.upper() not in [v.upper() for v in q.get("promo", [])]:
            continue
        if adults and str(adults) not in [v for v in q.get("adults", [])]:
            continue
        return True
    return False


def navigated_passenger_details(traj):
    return navigated_to_path(traj, "/en/booking/passenger-details.html")


def navigated_select_return(traj):
    return navigated_to_path(traj, "/en/booking/select-return.html")


def navigated_payment(traj):
    return navigated_to_path(traj, "/en/booking/payment.html")


def navigated_confirmation(traj):
    return navigated_to_path(traj, "/en/booking/confirmation.html")


def navigated_manage_lookup(traj):
    return navigated_to_path(traj, "/en/manage-booking.html")


def navigated_manage_booking(traj, pnr):
    return any(normalized_url_path(u) == f"/en/manage-booking/{pnr.upper()}.html"
               for u in site_urls(traj))


def navigated_checkin_lookup(traj):
    return navigated_to_path(traj, "/en/check-in.html")


def navigated_checkin(traj, pnr):
    return any(normalized_url_path(u) == f"/en/check-in/{pnr.upper()}.html"
               for u in site_urls(traj))


def navigated_boarding_pass(traj, pnr):
    return any(normalized_url_path(u) == f"/en/check-in/{pnr.upper()}/boarding-pass.html"
               for u in site_urls(traj))


def navigated_flight_status(traj, mode=None, number=None, origin=None, dest=None):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/en/flight-status.html":
            continue
        q = _query_params(u)
        if mode and mode not in q.get("mode", []):
            continue
        if number:
            wanted = re.sub(r"^QR", "", number.upper(), flags=re.I)
            got = [re.sub(r"^QR", "", v.upper()) for v in q.get("number", [])]
            if wanted not in got:
                continue
        if origin and origin.upper() not in [v.upper() for v in q.get("from", [])]:
            continue
        if dest and dest.upper() not in [v.upper() for v in q.get("to", [])]:
            continue
        return True
    return False


def navigated_destinations(traj, region=None, query=None):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/en/destinations.html":
            continue
        q = _query_params(u)
        if region and region not in q.get("region", []):
            continue
        if query and unquote(query).lower() not in [v.lower() for v in q.get("q", [])]:
            continue
        return True
    return False


def navigated_destination_guide(traj, slug):
    return any(normalized_url_path(u) == f"/en/destinations/{slug}.html"
               for u in site_urls(traj))


def navigated_offer(traj, slug=None):
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if path == "/en/offers.html" and slug is None:
            return True
        if slug and path == f"/en/offers/{slug}.html":
            return True
    return False


def navigated_pc(traj, page=None):
    for u in site_urls(traj):
        path = normalized_url_path(u).casefold()
        if not path.startswith("/en/privilege-club/"):
            continue
        if page is None or path == f"/en/privilege-club/{page.casefold()}.html":
            return True
    return False


def navigated_baggage(traj, fare=None, route=None):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/en/baggage.html":
            continue
        q = _query_params(u)
        if fare and fare not in q.get("fare", []):
            continue
        if route and route not in q.get("route", []):
            continue
        return True
    return False


def navigated_fleet(traj, code=None):
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if path == "/en/our-fleet.html" and code is None:
            return True
        if code and path.casefold() == f"/en/our-fleet/{code.casefold()}.html":
            return True
    return False


def navigated_help(traj, query=None):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/en/help.html":
            continue
        if query is None:
            return True
        q = _query_params(u)
        if unquote(query).lower() in [v.lower() for v in q.get("q", [])]:
            return True
    return False


def input_texts(traj):
    values = []
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        action = normalize_text(step.get("action"))
        if action not in INPUT_ACTIONS:
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
        elif isinstance(step.get("text"), str):
            values.append(str(step["text"]))
    return values


def entered_text_containing(traj, fragment):
    frag = normalize_text(fragment)
    return any(frag in normalize_text(v) for v in input_texts(traj))


# ---------------------------------------------------------------- deterministic answer match
def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = (text.replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "-").replace("\u2026", "..."))
    return re.sub(r"\s+", " ", text).strip().casefold()


neg = normalize_text

_NEGATION = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|doesn't|dont|doesn|don't|aren't|arent)"


def _affirmative(text, match):
    before = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()],
                     flags=re.I)[-1].split()[-3:]
    if any(re.fullmatch(_NEGATION, w, re.I) for w in before):
        return False
    return not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b",
                        text[match.end():], re.I)


def contains_all(text, tokens):
    t = normalize_text(text)
    return all(bool(tok) and any(_affirmative(t, m) for m in
                                 re.finditer(r"(?<!\w)" + re.escape(normalize_text(tok)) + r"(?!\w)", t))
               for tok in tokens)


def contains_any(text, tokens):
    t = normalize_text(text)
    return any(bool(tok) and any(_affirmative(t, m) for m in
                                 re.finditer(r"(?<!\w)" + re.escape(normalize_text(tok)) + r"(?!\w)", t))
               for tok in tokens)


def contains_amount(text, amount):
    """The answer quotes a USD amount, with or without separators/currency."""
    t = normalize_text(text)
    a = str(amount)
    variants = {a, f"{amount:,}", f"usd {a}", f"usd {amount:,}", f"${a}",
                f"${amount:,}", f"{a} usd", f"{amount:,} usd"}
    if any(v in t for v in variants):
        return True
    # tolerate '1.490' style thousands or 'USD 1,490.00' renderings
    return bool(re.search(rf"(?<!\d){re.escape(a).replace(',', '[,.]?')}(?!\d)", t))


def contains_time(text, hhmm):
    t = normalize_text(text)
    return hhmm in t or hhmm.replace(":", "") in t.replace(":", "")


# ---------------------------------------------------------------- SQLite snapshots
def _connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def table_rows(db_path, table):
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]


def table_count(db_path, table):
    with _connect(db_path) as conn:
        return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def changed_tables(initial_db, after_db, tables=None):
    tables = tables or TABLES
    changed = []
    for t in tables:
        try:
            if table_rows(initial_db, t) != table_rows(after_db, t):
                changed.append(t)
        except sqlite3.Error:
            changed.append(t)
    return changed


def row_delta(initial_db, after_db, table, key):
    initial_keys = {str(r[key]) for r in table_rows(initial_db, table)}
    return [r for r in table_rows(after_db, table) if str(r[key]) not in initial_keys]


def find_booking(db_path, pnr):
    for r in table_rows(db_path, "bookings"):
        if r["pnr"].upper() == pnr.upper():
            return r
    return None


def booking_legs(db_path, booking_id):
    return [r for r in table_rows(db_path, "booking_legs") if r["booking_id"] == booking_id]


def booking_passengers(db_path, booking_id):
    return [r for r in table_rows(db_path, "passengers") if r["booking_id"] == booking_id]


def user_by_email(db_path, email):
    for r in table_rows(db_path, "users"):
        if r["email"].lower() == email.lower():
            return r
    return None


def added_booking_matching(after_db, initial_db, *, cabin=None, fare_type=None,
                           adults=None, children=None, promo_code=None,
                           pc_number=None, status="confirmed", total=None,
                           origin=None, dest=None, leg_date=None,
                           flight_numbers=None, tol=0):
    """The single booking row added by the run, matching every given field.
    Runtime-random fields (pnr, ids) are matched structurally, never by value."""
    added = row_delta(initial_db, after_db, "bookings", "pnr")
    matches = []
    for b in added:
        if cabin is not None and b["cabin"] != cabin:
            continue
        if fare_type is not None and b["fare_type"] != fare_type:
            continue
        if adults is not None and b["adults"] != adults:
            continue
        if children is not None and b["children"] != children:
            continue
        if promo_code is not None and (b["promo_code"] or "") != promo_code:
            continue
        if pc_number is not None and (b["pc_number"] or "") != pc_number:
            continue
        if status is not None and b["status"] != status:
            continue
        if total is not None and abs(int(b["total_paid"]) - int(total)) > tol:
            continue
        legs = booking_legs(after_db, b["id"])
        if origin is not None and (not legs or legs[0]["origin_code"] != origin):
            continue
        if dest is not None and (not legs or legs[0]["dest_code"] != dest):
            continue
        if leg_date is not None and (not legs or legs[0]["leg_date"] != leg_date):
            continue
        if flight_numbers is not None:
            if sorted(l["flight_number"] for l in legs) != sorted(flight_numbers):
                continue
        matches.append(b)
    return matches[0] if len(matches) == 1 else None


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


def check_read_only(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    return judge.check("read_only_run", not changed,
                       f"expected no table changes, changed={changed!r}")


# ---------------------------------------------------------------- seed identity gate
def check_seed_identity(judge, initial_db):
    """The initial DB must BE the frozen seed (schema + rows + counts)."""
    try:
        with _connect(initial_db) as conn:
            schema_rows = conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "ORDER BY type, name").fetchall()
            schema_digest = hashlib.sha256(
                json.dumps(schema_rows, separators=(",", ":"), default=str).encode()).hexdigest()
            ok_schema = schema_digest == SEED_SCHEMA_SHA256
            rows_blob = []
            for t in TABLES:
                cur = conn.execute(f'SELECT * FROM "{t}" ORDER BY 1, 2')
                cols = [d[0] for d in cur.description]
                for r in cur:
                    rows_blob.append([t, dict(zip(cols, r))])
            rows_digest = hashlib.sha256(
                json.dumps(rows_blob, separators=(",", ":"), default=str,
                           ensure_ascii=False).encode()).hexdigest()
            ok_rows = rows_digest == SEED_ROWS_SHA256
            counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                      for t in TABLES}
            ok_counts = counts == SEED_COUNTS
    except sqlite3.Error as exc:
        return judge.check("seed_identity", False, f"unreadable initial DB: {exc}")
    ok = ok_schema and ok_rows and ok_counts
    detail = (f"schema={'ok' if ok_schema else 'BAD'}, "
              f"rows={'ok' if ok_rows else 'BAD'}, "
              f"counts={'ok' if ok_counts else 'BAD: ' + json.dumps(counts)}")
    return judge.check("seed_identity", ok, detail)


# ---------------------------------------------------------------- package identity
def _png_decodes(path):
    try:
        from PIL import Image
    except ImportError:
        data = Path(path).read_bytes()
        return (data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33
                and data[12:16] == b"IHDR")
    try:
        with Image.open(path) as image:
            image.load()
            return image.format == "PNG" and image.width >= 1 and image.height >= 1
    except Exception:  # noqa: BLE001
        return False


def check_trajectory_identity(judge, traj, task_id):
    judge.check("task_id", traj.get("task_id") == task_id,
               f"expected {task_id!r}, got {traj.get('task_id')!r}")
    judge.check("terminated", bool(traj.get("terminated")),
               f"terminated={traj.get('terminated')!r}, reason={traj.get('termination_reason')!r}")
    judge.check("nonempty_answer", len(final_answer(traj)) > 0,
               f"final answer length {len(final_answer(traj))}")
    start = str(traj.get("start_url") or "")
    same_origin = True
    for u in site_urls(traj):
        a, b = urlparse(u), urlparse(start)
        try:
            if (a.port or 80) != (b.port or 80) or a.hostname.casefold() != b.hostname.casefold():
                same_origin = False
        except ValueError:
            same_origin = False
    judge.check("same_origin", same_origin and bool(start), f"start_url={start!r}")
    shots = traj.get("_shots") or {}
    ok_shots = True
    for step in traj.get("steps") or []:
        if isinstance(step, dict) and step.get("screenshot"):
            p = shots.get(str(step["screenshot"]))
            if p is None or not _png_decodes(p):
                ok_shots = False
                break
    judge.check("screenshots_decode", ok_shots, f"{len(shots)} shots in run dir")


# ---------------------------------------------------------------- harness
class Judge:
    def __init__(self, task_id):
        self.task_id = task_id
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence=""):
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name  # the FIRST failing check
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
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True,
                     "reason": reason,
                     "evidence": [f"[FAIL] {reason}: {detail}"]},
                    ensure_ascii=False, indent=2))
    sys.exit(1)


# ---------------------------------------------------------------- CLI
def _parse_args(argv):
    """simpleArgParser-compatible flag parsing (booleans take a value)."""
    flags = {"--run_dir": "", "--initial_db": "", "--after_db": "",
             "--container": DEFAULT_CONTAINER, "--no_llm": "False"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            if i + 1 < len(argv):
                flags[a] = argv[i + 1]
                i += 2
            else:
                i += 1
        else:
            i += 1
    return flags


def _docker_cp(container, remote, local):
    remote_path = f"/opt/WebSyn/{SITE}/{remote}"
    result = subprocess.run(["docker", "cp", f"{container}:{remote_path}", local],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"docker cp {remote_path}: {result.stderr.strip()[:200]}")


def resolve_snapshots(args, task_id):
    initial_db, after_db = args["--initial_db"], args["--after_db"]
    run = Path(args["--run_dir"])
    if not initial_db and (run / "initial.db").is_file():
        initial_db = str(run / "initial.db")
    if not after_db and (run / "after.db").is_file():
        after_db = str(run / "after.db")
    if not initial_db or not after_db:
        tmp = Path(tempfile.mkdtemp(prefix=f"wh-qa-verify-{task_id}-"))
        container = args["--container"]
        if not initial_db:
            seed = Path(__file__).resolve().parent.parent / "instance_seed" / "qatar_airways.db"
            if seed.is_file():
                initial_db = str(seed)
            else:
                if not container:
                    fail_closed(task_id, "no_initial_db",
                                "no initial.db in run dir, no local instance_seed, no container")
                initial_db = str(tmp / "initial.db")
                _docker_cp(container, "instance_seed/qatar_airways.db", initial_db)
        if not after_db:
            live = Path(__file__).resolve().parent.parent / "instance" / "qatar_airways.db"
            if live.is_file():
                after_db = str(live)
            else:
                if not container:
                    fail_closed(task_id, "no_after_db",
                                "no after.db in run dir, no local instance, no container")
                after_db = str(tmp / "after.db")
                _docker_cp(container, "instance/qatar_airways.db", after_db)
    return initial_db, after_db


def run_verifier(task_id, run_checks):
    """Standard main(): load the run, resolve + gate the snapshots, run the
    task checks, fail closed on any error."""
    args = _parse_args(sys.argv[1:])
    if not args["--run_dir"]:
        fail_closed(task_id, "missing_run_dir", "--run_dir is required")
    try:
        traj = load_run(args["--run_dir"])
    except (OSError, ValueError) as exc:
        fail_closed(task_id, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, task_id)
    judge = Judge(task_id)
    try:
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()
