#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for
Medicare.gov (medicare_gov) task verification.

Contract rebuilt for the 15 redesigned deep tasks (depth-review round 2). The
harness is the hardened WebHarbor verifier harness (lineage: sites/landwatch,
sites/imgur, then the first medicare_gov review contract @ 729f1517); the
frozen-seed contract is unchanged (same seed file, same digests).

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names (coverage search + detail pages, costs
     page, get-started / fraud / talk pages, care-compare search results,
     provider detail pages, DME results, plan finder results, publications
     search + order forms, log-in, the MyMedicare claims / premiums / messages /
     message-detail / account-settings / replacement-card pages).
  3. Answer check: affirmative token / phrase / money / count / phone / MBI
     matching against frozen ground truth HARDCODED in each ``verify_N.py``
     (never in tasks.jsonl).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require every table row-identical; login-read tasks allow
     exactly one ``login_events`` insert for the named benchmark user (task 7
     additionally tolerates the optional newest-message-opened flip; task 12
     requires it); stateful tasks require the exact allowed row deltas and
     nothing else (premium bill Due->Paid with method, mailing address supersede
     + insert, card_requests insert, pub_orders inserts).
  5. LLM utilities are kept for parity with the other suites. They are anchored
     on ground truth, make one call each, and are NEVER load-bearing: every
     verdict is decided with ``--no_llm True`` and the helpers only add
     ``[INFO]`` evidence.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-review)
  --no_llm True         skip the advisory LLM evidence (verdicts never depend on it)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.

Frozen-seed note: the seed is rebuilt deterministically (PYTHONHASHSEED=0, fixed
scrypt password digest, .build-generated-seed). The physical file layout differs
between sqlite builds (host vs container) but the logical content is frozen; the
verifiers pin SCHEMA_SHA256 + SEED_ROWS_SHA256 (both verified identical between a
host build and the review-container build) and compare snapshots logically.
"""
# NOTE: no `from __future__ import annotations` here — simpleArgParser reads the
# dataclass field types at runtime and needs real types, not strings.
import atexit
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
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

SITE = "medicare_gov"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# The frozen snapshot instant (app.MIRROR_REFERENCE_DATE).
MIRROR_REFERENCE_DATE = "2026-09-23"

# ---------------------------------------------------------------- frozen seed contract
TABLES = (
    "card_requests", "claims", "content_pages", "cost_amounts", "county_zips",
    "coverage_items", "coverage_topics", "dme_suppliers", "dme_zip_rows", "dme_zips",
    "equipment_categories", "login_events", "mailing_addresses", "messages",
    "payment_methods", "plans", "premium_bills", "provider_cities", "providers",
    "pub_orders", "publications", "subscriber_emails", "users",
)
SEED_COUNTS = {
    "card_requests": 0, "claims": 12, "content_pages": 13, "cost_amounts": 25,
    "county_zips": 32, "coverage_items": 165, "coverage_topics": 6,
    "dme_suppliers": 472, "dme_zip_rows": 472, "dme_zips": 8,
    "equipment_categories": 79, "login_events": 8, "mailing_addresses": 4,
    "messages": 11, "payment_methods": 8, "plans": 55, "premium_bills": 8,
    "provider_cities": 8, "providers": 3121, "pub_orders": 0, "publications": 84,
    "subscriber_emails": 0, "users": 4,
}
# sha256 over sqlite_master (type, name, tbl_name, sql) of the frozen seed.
# Verified identical between a host build (md5 ec01a677...) and the review
# container build (md5 8165aea5...): same logical content, different page layout.
SCHEMA_SHA256 = "644925b38e3cb52c8e7e673c61d4a0b753745a108103e231d4d011c215c43e6a"
# sha256 over every seed row (table-canonical, ORDER BY all columns).
SEED_ROWS_SHA256 = "1ebd3c7afe9813627bbd46ad4820f45a103669d50eb62f07e210ac500e8d17ed"

SEED_USERS = {  # email -> (id, display_name); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson"),
    "bob.c@test.com": (2, "Bob Chen"),
    "carol.d@test.com": (3, "Carol Davis"),
    "david.k@test.com": (4, "David Kim"),
}
DEMO_PASSWORD = "TestPass123!"
# seed_data.BENCHMARK_PASSWORD_HASH — the frozen scrypt digest for DEMO_PASSWORD.
BENCHMARK_PASSWORD_HASH = (
    "scrypt:32768:8:1$webharbor-medicare-fixed-salt$"
    "f2986073a98bda3c6d193d522b20c2bb8ef28d14939dc0305b827669def78a47"
    "3acca8fcd344b8dacadd6215095976476d65cdc19e8c4c23ea8a04bd0fe48157"
)
# Login form carries a hidden device field; every honest login writes exactly
# one deterministic login_events row.
LOGIN_EVENT_METHOD = "Medicare.gov account"
LOGIN_EVENT_DEVICE = "Chrome on Windows"

# Seed natural keys the stateful verifiers pin (never positional row ids).
ALICE_EMAIL = "alice.j@test.com"
BOB_EMAIL = "bob.c@test.com"
CANCER_PUB_NUMBER = "11931"          # Medicare Coverage of Cancer Treatment Services
MEDIGAP_PUB_NUMBER = "02110"         # Choosing a Medigap Policy
HANDBOOK_PUB_NUMBER = "10050"        # Medicare & You 2027 (anonymous-order task)
COLONOSCOPY_DESCRIPTION = "Screening colonoscopy"
BOB_DUE_BILL_AMOUNT = "$202.90"
BOB_DUE_BILL_DUE_DATE = "2026-10-25"
DEFAULT_PAYMENT_LABEL = "Bank account ending 4821"
NEW_ADDRESS = ("45 Meadow Lane", "Buffalo Grove", "IL", "60089")   # task 9 (alice)
NEW_ADDRESS_BOB = ("789 Oak Street", "Oak Park", "IL", "60302")     # task 8 (bob)
ANON_ADDRESS = ("302 W Edwards St", "Springfield", "IL", "62704")  # task 11 (anonymous)
ALICE_MBI = "1EG4-TE5-MK73"
# The message-center rows the redesigned account tasks reference (task 7 reads
# the newest unread subject from the list; task 12 opens it and reads the body).
NEWEST_UNREAD_MESSAGE_ID = 3
NEWEST_UNREAD_SUBJECT = "Reminder: Medicare Open Enrollment starts October 15"
OPEN_ENROLLMENT_DATES = "October 15 through December 7, 2026"

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
    """Every browser URL the recorder wrote: start_url, each step's url (+url_after), final_url."""
    urls: list[str] = []
    if traj.get("start_url"):
        urls.append(str(traj["start_url"]))
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_after"):
            if step.get(key):
                urls.append(str(step[key]))
    if traj.get("final_url"):
        urls.append(str(traj["final_url"]))
    return urls


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def final_url(traj):
    if traj.get("final_url"):
        return str(traj["final_url"])
    for step in reversed(traj.get("steps") or []):
        if isinstance(step, dict) and step.get("url"):
            return str(step["url"])
    return ""


def normalized_url_path(url):
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def is_site_url(url):
    """HTTP(S) URL on a loopback host (any port: alt-port containers are legitimate)."""
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


def navigated_to(traj, substr, times=1):
    """At least `times` recorded on-site URLs contain substr."""
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def _query_params(url):
    return {k: [unquote(v) for v in vals] for k, vals in
            parse_qs(urlparse(str(url)).query, keep_blank_values=True).items()}


def query_of_path(traj, expected_path):
    """Concatenated query strings of every on-site URL whose path == expected_path.

    Values are URL-decoded and '+' (form-encoding space) is normalized to a
    space so token checks like 'family practice' match 'family+practice'."""
    expected = normalized_url_path(expected_path)
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == expected:
            out.append(unquote(urlparse(str(u)).query or "").replace("+", " "))
    return " ".join(out).casefold()


def navigated_to_path_with_params(traj, expected_path, params, any_param=None):
    """Some on-site URL whose path matches AND whose query carries the exact
    key/value pairs (value match is exact after URL-decoding). `any_param` is a
    (key, [values]) pair where any of the values is acceptable."""
    expected = normalized_url_path(expected_path)
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = _query_params(u)
        if all(str(value) in query.get(key, []) for key, value in params.items()):
            if any_param is None:
                return True
            key, values = any_param
            if any(v in query.get(key, []) for v in values):
                return True
    return False


def input_texts(traj):
    values = []
    for step in traj.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in INPUT_ACTIONS:
            continue
        params = step.get("params")
        if isinstance(params, dict) and params.get("text") is not None:
            values.append(str(params["text"]))
    return values


def entered_identity(traj, *identities):
    wanted = {normalize_text(i) for i in identities}
    return any(normalize_text(v) in wanted for v in input_texts(traj))


# ---------------------------------------------------------------- deterministic answer match
def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text

_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)"


def _match_is_affirmative(text, match):
    # Negation window: a negation word invalidates the match only when it sits
    # within the last three words before it.
    before_words = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()],
                           flags=re.I)[-1].split()[-3:]
    if any(re.fullmatch(_NEGATION_WORDS, w, re.I) for w in before_words):
        return False
    after = text[match.end():]
    return not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I)


def _affirmative_search(pattern, text, flags=0):
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags=re.I))


def answer_equals(final, expected):
    return normalize_text(final) == normalize_text(expected)


def contains_all(text, tokens):
    normalized = normalize_text(text)
    return all(bool(t) and _affirmative_search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", normalized)
               for t in (normalize_text(x) for x in tokens))


def contains_any(text, tokens):
    normalized = normalize_text(text)
    return any(bool(t) and _affirmative_search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", normalized)
               for t in (normalize_text(x) for x in tokens))


def contains_phrase(text, phrase):
    """Whole-word phrase match tolerant of hyphen/space joins."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def contains_all_phrases(text, phrases):
    return all(contains_phrase(text, p) for p in phrases)


def contains_any_phrase(text, phrases):
    return any(contains_phrase(text, p) for p in phrases)


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
    19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
    70: "seventy", 80: "eighty", 90: "ninety",
}


def _number_word(n):
    if n in _NUMBER_WORDS:
        return _NUMBER_WORDS[n]
    if 21 <= n <= 99:
        tens, ones = divmod(n, 10)
        return f"{_NUMBER_WORDS[tens * 10]}-{_NUMBER_WORDS[ones]}"
    return None


def _digit_forms(number):
    s = str(int(number))
    grouped = ""
    tail = s
    while len(tail) > 3:
        grouped = "," + tail[-3:] + grouped
        tail = tail[:-3]
    grouped = tail + grouped
    return [re.escape(s), re.escape(grouped), re.escape(grouped).replace(r"\,", r"\s?")]


def contains_count(text, number):
    """`number` as a standalone integer (not inside a longer digit run, a decimal,
    a thousands group or an ordinal), tolerant of thousands separators, or its
    English word."""
    normalized = normalize_text(text)
    n = int(number)
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])" + form + r"(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
        if _affirmative_search(pattern, normalized):
            return True
    word = _number_word(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_money(text, dollars, cents=0):
    """'$202.90' == '202.90' == '$202.90/month'. Cents are optional when 0,
    required (either '.90' or '90 cents') when non-zero... here: exact decimal
    dollars with optional thousands separators and optional leading '$'."""
    normalized = normalize_text(text)
    n = int(dollars)
    if cents:
        dec = f"{n}.{cents:02d}"
        forms = [re.escape(dec), re.escape(f"{n},{dec}"), re.escape(f"{n:,}.{cents:02d}")]
        for form in forms:
            pattern = r"(?<![\d.,])[$]?\s*" + form.replace(r"\,", r"\s?") + r"(?!\d)"
            if _affirmative_search(pattern, normalized):
                return True
        # "$202 and 90 cents" style
        if _affirmative_search(rf"(?<![\d.,])[$]?\s*{n}\s*(?:dollars?|and)\s*(?:\+\s*)?{cents}\s*cents?", normalized):
            return True
        return False
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])[$]?\s*" + form + r"(?!\d|[.,]\d)"
        if _affirmative_search(pattern, normalized):
            return True
    return False


def contains_phone(text, digits10):
    """'(713) 665-4747' == '713-665-4747' == '713.665.4747' == '7136654747'."""
    normalized = normalize_text(str(text))
    d = re.sub(r"\D", "", str(digits10))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10:
        raise ValueError("contains_phone wants a 10-digit number")
    pattern = r"\+?1?[\s.\-(]*" + d[:3] + r"[\s.\-)]*" + d[3:6] + r"[\s.\-]*" + d[6:]
    return _affirmative_search(pattern, normalized)


def contains_medicare_number(text, mbi):
    """'1EG4-TE5-MK73' == '1EG4 TE5 MK73' == '1eg4te5mk73'."""
    normalized = normalize_text(text)
    parts = [re.escape(p) for p in mbi.split("-")]
    pattern = r"(?<![a-z0-9])" + r"[\s-]*".join(parts) + r"(?![a-z0-9])"
    return _affirmative_search(pattern, normalized)


# ---------------------------------------------------------------- DB state
def db_query(db_path, sql, params=()):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def fetch_db(container, kind):
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    fd, path = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip() or r.stdout.strip()}")
    atexit.register(Path(path).unlink, missing_ok=True)
    return path


def resolve_db(arg, container, kind):
    if arg:
        return str(arg) if Path(arg).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None  # caller treats None as "unavailable" and fails closed


def table_columns(db_path, table):
    return [row["name"] for row in db_query(db_path, f"PRAGMA table_info({table})")]


def _order_clause(db_path, table):
    cols = table_columns(db_path, table)
    return ",".join(f"[{c}]" for c in cols)


def table_rows(db_path, table):
    """Environment-independent full-table scan (ORDER BY all columns)."""
    order = _order_clause(db_path, table)
    return [tuple(row) for row in db_query(db_path, f"SELECT {order} FROM [{table}] ORDER BY {order}")]


def rows_by_id(db_path, table):
    cols = table_columns(db_path, table)
    d = {c: i for i, c in enumerate(cols)}
    out = {}
    for row in table_rows(db_path, table):
        out[row[d["id"]]] = row
    return out


def table_delta(initial_db, after_db, table):
    before, after = rows_by_id(initial_db, table), rows_by_id(after_db, table)
    return {
        "added": [after[k] for k in sorted(set(after) - set(before))],
        "removed": [before[k] for k in sorted(set(before) - set(after))],
        "changed": [(before[k], after[k]) for k in sorted(set(before) & set(after))
                    if before[k] != after[k]],
    }


def changed_tables(initial_db, after_db, tables=TABLES):
    return [t for t in tables if table_rows(initial_db, t) != table_rows(after_db, t)]


def row_dict(db_path, table, row):
    return dict(zip(table_columns(db_path, table), row))


def _schema_objects(db_path):
    return [tuple(r) for r in db_query(
        db_path,
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]


def schema_sha256(db_path):
    return hashlib.sha256(json.dumps(_schema_objects(db_path), separators=(",", ":")).encode()).hexdigest()


def rows_digest(db_path, tables=TABLES):
    h = hashlib.sha256()
    for table in tables:
        for row in table_rows(db_path, table):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def validate_snapshot_contract(initial_db, after_db):
    """Raise ValueError unless both snapshots are genuine medicare_gov databases
    derived from the frozen seed."""
    for db_path in (initial_db, after_db):
        tables = {r["name"] for r in db_query(
            db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(TABLES):
            raise ValueError(f"unexpected tables in {db_path}: {sorted(tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed_hash = schema_sha256(initial_db)
    if observed_hash != SCHEMA_SHA256:
        raise ValueError(f"unsupported medicare_gov schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["display_name"])
             for r in db_query(initial_db, "SELECT id, display_name, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    hash_row = db_query(initial_db, "SELECT password_hash FROM users WHERE email=?", (ALICE_EMAIL,))
    if not hash_row or hash_row[0][0] != BENCHMARK_PASSWORD_HASH:
        raise ValueError("benchmark user password hash differs from the frozen seed")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen medicare_gov seed: rows digest {digest}")
    # benchmark users keep their identity columns in the after snapshot
    after_users = {r["email"]: (int(r["id"]), r["display_name"])
                   for r in db_query(after_db, "SELECT id, display_name, email FROM users")}
    if any(after_users.get(email) != ident for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) medicare_gov database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- medicare_gov-specific state helpers
def user_id_by_email(db_path, email):
    rows = db_query(db_path, "SELECT id FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return int(rows[0][0]) if rows else None


def login_events_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM login_events WHERE user_id = ? ORDER BY id", (user_id,))]


def expected_login_event(user_id):
    """The deterministic row the app writes for one honest login."""
    return {"user_id": user_id, "when": MIRROR_REFERENCE_DATE,
            "method": LOGIN_EVENT_METHOD, "device": LOGIN_EVENT_DEVICE}


def _login_event_matches(row, user_id):
    return (int(row["user_id"]) == int(user_id)
            and str(row["when"]) == MIRROR_REFERENCE_DATE
            and str(row["method"]) == LOGIN_EVENT_METHOD
            and str(row["device"]) == LOGIN_EVENT_DEVICE)


def check_login_delta(judge, initial_db, after_db, email, extra_allowed=()):
    """Exactly one new login_events row for the named user (the honest login) and
    nothing else anywhere except the extra allowed table names."""
    user_id = user_id_by_email(initial_db, email)
    if user_id is None:
        judge.check("benchmark_user_exists", False, f"missing user {email!r}")
        return
    delta = table_delta(initial_db, after_db, "login_events")
    added = [row_dict(after_db, "login_events", r) for r in delta["added"]]
    ok = (len(added) == 1 and not delta["removed"] and not delta["changed"]
          and _login_event_matches(added[0], user_id))
    judge.check("exactly_one_login_event", ok,
                f"added={[{k: a[k] for k in ('id','user_id','when','method','device')} for a in added]!r}, "
                f"removed={len(delta['removed'])}, changed={len(delta['changed'])}")
    others = tuple(t for t in TABLES if t != "login_events" and t not in set(extra_allowed))
    changed = changed_tables(initial_db, after_db, others)
    judge.check("no_collateral_writes", not changed, f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


def check_read_only(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    return judge.check("read_only_db_unchanged", not changed, f"changed_tables={changed!r}")


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    """Every table outside `allowed` is row-identical before/after."""
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


def pub_id_by_number(db_path, product_number):
    rows = db_query(db_path, "SELECT id FROM publications WHERE product_number = ? LIMIT 1", (str(product_number),))
    return int(rows[0][0]) if rows else None


def pub_orders_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM pub_orders WHERE user_id = ? ORDER BY id", (user_id,))]


def premium_bills_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM premium_bills WHERE user_id = ? ORDER BY id", (user_id,))]


def mailing_addresses_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM mailing_addresses WHERE user_id = ? ORDER BY id", (user_id,))]


def messages_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM messages WHERE user_id = ? ORDER BY id", (user_id,))]


def check_message_read_delta(judge, initial_db, after_db, user_id, require_opened):
    """The messages table carries at most the single honest is_read flip of the
    newest unread message (id NEWEST_UNREAD_MESSAGE_ID). Task 12 opens the
    message (flip required); task 7 may read the subject from the list (flip
    optional). Any other messages change fails."""
    delta = table_delta(initial_db, after_db, "messages")
    pairs = delta["changed"]  # list of (before_row, after_row) tuples
    before = [row_dict(initial_db, "messages", b) for b, a in pairs]
    changed = [row_dict(after_db, "messages", a) for b, a in pairs]
    honest = (len(changed) == 1 and not delta["added"] and not delta["removed"]
              and int(changed[0]["id"]) == NEWEST_UNREAD_MESSAGE_ID
              and int(before[0]["is_read"]) == 0 and int(changed[0]["is_read"]) == 1
              and int(changed[0]["user_id"]) == int(user_id))
    if require_opened:
        ok = honest
        judge.check("message_opened_is_read_flip", ok,
                    f"changed={changed!r}, before={before!r}")
    else:
        ok = honest or (not delta["added"] and not delta["removed"] and not delta["changed"])
        flips = [(b["id"], a["is_read"]) for b, a in zip(before, changed)]
        judge.check("messages_at_most_newest_unread_flip", ok,
                    f"delta_added={len(delta['added'])}, delta_removed={len(delta['removed'])}, "
                    f"delta_changed={flips!r}")
    return bool(ok)


def check_table_delta_shape(judge, initial_db, after_db, table,
                            allowed_changed_ids=(), allowed_added=0,
                            allowed_removed=0, label=""):
    """The table delta carries nothing beyond the explicitly allowed shape:
    at most `allowed_added` new rows, `allowed_removed` removed rows, and
    changed rows only within `allowed_changed_ids` (any user — a cross-user
    sneaky write inside an allowed table still fails)."""
    before, after = rows_by_id(initial_db, table), rows_by_id(after_db, table)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    ok = (len(added) == allowed_added and len(removed) == allowed_removed
          and set(changed) <= set(int(i) for i in allowed_changed_ids))
    judge.check(label or f"{table}_delta_shape", ok,
                f"table={table}, added={added!r}, removed={removed!r}, changed={changed!r}, "
                f"allowed_changed={list(allowed_changed_ids)!r}, allowed_added={allowed_added}, "
                f"allowed_removed={allowed_removed}")
    return bool(ok)


def card_requests_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM card_requests WHERE user_id = ? ORDER BY id", (user_id,))]


# ---------------------------------------------------------------- judge harness
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = bool(no_llm)
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name  # record the FIRST failing check
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
        from PIL import Image  # available in the agent_demo env (browser-use dependency)
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
    """The named demo account must have been entered on the log-in page."""
    judge.check("visited_login_page", navigated_to_path(traj, "/account/login"),
                "required_path=/account/login")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email),
                f"expected {email!r} in an input step; observed_inputs={input_texts(traj)!r}")


def check_visited_path(judge, traj, name, path):
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_coverage_lookup(judge, traj, slug, query_tokens):
    """The agent searched the coverage database and opened the item's detail page."""
    q = query_of_path(traj, "/coverage/search")
    searched = any(tok in q for tok in query_tokens) or navigated_to_path(traj, "/coverage/popular-topics") \
        or navigated_to_path(traj, "/coverage/find-alphabetically")
    judge.check("searched_or_browsed_coverage",
                searched,
                f"query_text={q!r}, popular_topics={navigated_to_path(traj, '/coverage/popular-topics')}, "
                f"alpha={navigated_to_path(traj, '/coverage/find-alphabetically')}")
    judge.check(f"opened_coverage_detail_{slug}",
                navigated_to_path(traj, f"/coverage/{slug}"),
                f"required_path=/coverage/{slug}")


# ---------------------------------------------------------------- anchored LLM utilities (advisory only)
_NO_LLM = False


def _llm_config():
    return (os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("JUDGE_MODEL", ""))


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint. Returns text or None; never raises."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    url = base.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call anchored on the frozen ground truth (never on model knowledge)."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    return _verdict(_chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}]))


def advisory_llm_answer(judge, answer, ground_truth, question):
    """Record an [INFO] line from the anchored LLM helper when one is configured. Never load-bearing."""
    if judge.no_llm or not all(_llm_config()):
        return
    ok, why = llm_text_match(answer, ground_truth, question)
    judge.note("llm_answer_consistency_advisory", f"{'PASS' if ok else 'FAIL'}: {why[:200]}")


# ---------------------------------------------------------------- CLI
@dataclass
class VerifyArgs:
    run_dir: str = ""
    initial_db: str = ""
    after_db: str = ""
    container: str = DEFAULT_CONTAINER
    no_llm: bool = False

    def post_process(self):
        if not self.run_dir:
            raise SystemExit("--run_dir is required")
        run = Path(self.run_dir)
        if not self.initial_db and (run / "initial.db").is_file():
            self.initial_db = str(run / "initial.db")
        if not self.after_db and (run / "after.db").is_file():
            self.after_db = str(run / "after.db")


def parse_args():
    try:
        import simpleArgParser as sap  # the agent_demo env; boolean flags take a value: --no_llm True
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
    """Standard main(): load the run, resolve + validate snapshots, run the task checks, fail closed on error."""
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
