#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for
LandWatch task verification.

Structure follows the hardened WebHarbor verifier harnesses (sites/imgur/verify/verify_lib.py,
sites/chess_com/verify/verify_lib.py, sites/google_shopping/verify/verify_lib.py):

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty final
     answer, every recorded URL on the same loopback origin AND port as ``start_url``,
     every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the on-site
     surfaces the task names (state/city/county/region/category search pages with the
     price / parcel-size filters and sort query params, listing detail pages, find-agent
     directory, agent profiles, log-in, account pages).
  3. Answer check: affirmative token / phrase / money / acreage / count / date matching
     against frozen ground truth HARDCODED in each ``verify_N.py`` (never in tasks.jsonl).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only tasks
     require every table row-identical (sessions included — no login happens); login tasks
     allow exactly the ``sessions`` delta; stateful tasks require the exact allowed row
     delta and nothing else (saved_searches +/-, inquiries insert, users.phone update,
     one registered user row, favorites removal for task 20).
  5. LLM utilities are kept for parity with the other suites. They are anchored on ground
     truth, make one call each, and are NEVER load-bearing: every verdict is decided with
     ``--no_llm True`` and the helpers only add ``[INFO]`` evidence.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm True        skip the advisory LLM evidence (verdicts never depend on it)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
# NOTE: no `from __future__ import annotations` here — simpleArgParser reads the dataclass
# field types at runtime and needs real types, not strings.
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

SITE = "landwatch"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("listings", "agents", "regions", "counties", "cities", "property_types",
          "home_featured", "category_tiles", "static_pages", "users", "favorites",
          "saved_searches", "inquiries", "sessions")
SEED_COUNTS = {"listings": 436, "agents": 313, "regions": 29, "counties": 318,
               "cities": 377, "property_types": 11, "home_featured": 7,
               "category_tiles": 8, "static_pages": 1, "users": 4, "favorites": 18,
               "saved_searches": 7, "inquiries": 3, "sessions": 0}
# sha256 over sqlite_master (type, name, tbl_name, sql) of the frozen seed.
SCHEMA_SHA256 = "ab858e24aecf2ae9dc2b1a63fda2b3bd0ec0d08a0737fb96385f4f67476a047f"
# sha256 over every seed row (table-scanonical, ORDER BY all columns). The seed is rebuilt
# deterministically at image-build time (PYTHONHASHSEED=0, frozen password hashes, see
# .build-generated-seed); the physical file layout may differ between sqlite builds but
# this logical digest is frozen.
# Audit refresh (dead-link fix): the two benchmark saved-search URLs that pointed at
# non-existent filter buckets (/hunting-property/price-under-249999 ->
# /hunting-property/price-100000-249999, /colorado-land-for-sale/acres-over-100 ->
# /colorado-land-for-sale/acres-101-200) were repaired; saved-search NAMES (which the
# task-10 ground truth checks) are unchanged, so only this rows digest moves.
SEED_ROWS_SHA256 = "9c80b8350247aba0bd535ecfae7be613bb7bf212c769e0612394415d7dec7733"
SEED_USERS = {  # email -> (id, name); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson"),
    "bob.c@test.com": (2, "Bob Chen"),
    "carol.d@test.com": (3, "Carol Davis"),
    "david.k@test.com": (4, "David Kim"),
}
DEMO_PASSWORD = "TestPass123!"
PASSWORD_NAMESPACE = "landwatch-webharbor-demo"
REGISTERED_EMAIL = "new.landbuyer@test.com"
REGISTERED_PASSWORD_HASH = "b35294c904271b106649528602ef203b3b3621b3c14f7ea81e051a702a1791e7"
# primary key columns per table (delta keys); default "id"
PK_COLUMNS = {"sessions": ["token"], "listings": ["pid"], "agents": ["account_id"]}
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}


def stable_password_hash(raw_password: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PASSWORD_NAMESPACE}:{raw_password}".encode("utf-8"))
    return digest.hexdigest()


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
    # Reference identifiers/annotations are not assertions of a requested fact.
    text = str(traj.get("final_answer") or "").strip()
    text = re.sub(r"(?m)^\s*[-*]\s*", "", text)
    return re.sub(r"\([^)]*\b(?:reference|ref\.?|sku)\b[^)]*\)", "", text, flags=re.I)


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


def navigated_to_path_with_params(traj, expected_path, params, any_param=None):
    """Some on-site URL whose path matches AND whose query carries the exact key/value
    pairs (value match is exact after URL-decoding). `any_param` is a (key, [values])
    pair where any of the values is acceptable."""
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


def search_queries(traj):
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == "/search":
            for q in _query_params(u).get("q") or []:
                out.append(q)
    return out


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
    text = text.replace("\u00b1", "±")
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text

_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)"


def _match_is_affirmative(text, match):
    # Negation window: a negation word invalidates the match only when it sits within
    # the last three words before it.
    before_words = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()],
                           flags=re.I)[-1].split()[-3:]
    if any(re.fullmatch(_NEGATION_WORDS, w, re.I) for w in before_words):
        return False
    after = text[match.end():]
    return not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I)


def _affirmative_search(pattern, text, flags=0):
    return any(_match_is_affirmative(text, m) for m in re.finditer(pattern, text, flags))


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


def contains_phrase_without_prefix(text, phrase, forbidden_prefix):
    """Phrase present as a standalone word run NOT preceded by `forbidden_prefix`
    (e.g. 'Virginia' in a state list that must not be the 'West Virginia' entry)."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").split()]
    if not words:
        return False
    prefix = re.escape(normalize_text(forbidden_prefix).strip())
    pattern = r"(?<!\w)" + r"\s*".join(words) + r"(?!\w)"
    for m in re.finditer(pattern, normalize_text(text)):
        head = normalize_text(text)[: m.start()]
        if not re.search(prefix + r"\s*$", head):
            if _match_is_affirmative(normalize_text(text), m):
                return True
    return False


def phrases_in_order(text, phrases):
    normalized = normalize_text(text)
    cursor = 0
    for phrase in phrases:
        words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
        if not words:
            return False
        pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
        m = re.search(pattern, normalized[cursor:])
        if not m or not _match_is_affirmative(normalized[cursor:], m):
            return False
        cursor += m.end()
    return True


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty",
    40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
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
    """`number` as a standalone integer (not inside a longer digit run, a decimal, a
    thousands group or an ordinal), tolerant of thousands separators, or its English word."""
    normalized = normalize_text(text)
    n = int(number)
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])" + form + r"(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
        if _affirmative_search(pattern, normalized):
            return True
    word = _number_word(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_money(text, dollars):
    """'$6,100,000' == '6,100,000' == '$6100000' == '6100000' (currency symbol optional)."""
    normalized = normalize_text(text)
    n = int(dollars)
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])[$]?\s*" + form + r"(?!\d|[.,]\d)"
        if _affirmative_search(pattern, normalized):
            return True
    return False


def contains_acres(text, value):
    """'111 Acres' / '20.18 acres' / '11,764-acre' — acreage with optional decimals and
    thousands separators; the unit is required so a bare number does not match. For
    non-integer acreage only the exact decimal forms match (an answer of '20 Acres'
    must not satisfy a 20.18-acre ground truth)."""
    normalized = normalize_text(text)
    n = float(value)
    if n == int(n):
        bases = _digit_forms(int(n))
    else:
        bases = [re.escape(f"{n:g}"), re.escape(f"{n:.2f}"), re.escape(f"{n:.1f}")]
    for base in bases:
        for unit in (r"\s?acres?", r"\s?-acre\b", r"\s?ac\b"):
            pattern = r"(?<![\d.,])[$]?\s*" + base + unit
            if _affirmative_search(pattern, normalized):
                return True
    return False


_MONTHS = {"01": "january", "02": "february", "03": "march", "04": "april", "05": "may", "06": "june",
           "07": "july", "08": "august", "09": "september", "10": "october", "11": "november", "12": "december"}


def contains_iso_date(text, iso):
    """'2026-09-28' == 'September 28, 2026' == '09/28/2026' == 'Sep 28 2026'."""
    normalized = normalize_text(text)
    year, month, day = iso.split("-")
    month_name = _MONTHS[month]
    patterns = [
        re.escape(iso),
        rf"\b{month_name}\.?\s+{int(day)}\s*,?\s+{year}\b",
        rf"\b{month_name[:3]}\.?\s+{int(day)}\s*,?\s+{year}\b",
        rf"\b{int(month)}/{int(day)}/{year}\b",
        rf"\b{int(day)}\s+{month_name}\s+{year}\b",
    ]
    return any(_affirmative_search(p, normalized) for p in patterns)


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


def pk_of(db_path, table):
    cols = PK_COLUMNS.get(table, ["id"])
    present = table_columns(db_path, table)
    return [c for c in cols if c in present] or present[:1]


def rows_by_pk(db_path, table):
    keys = pk_of(db_path, table)
    out = {}
    for row in table_rows(db_path, table):
        cols = table_columns(db_path, table)
        d = dict(zip(cols, row))
        out[tuple(d[k] for k in keys)] = row
    return out


def table_delta(initial_db, after_db, table):
    before, after = rows_by_pk(initial_db, table), rows_by_pk(after_db, table)
    return {
        "added": [after[k] for k in sorted(set(after) - set(before), key=repr)],
        "removed": [before[k] for k in sorted(set(before) - set(after), key=repr)],
        "changed": [(before[k], after[k]) for k in sorted(set(before) & set(after), key=repr)
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
    """Raise ValueError unless both snapshots are genuine LandWatch databases derived
    from the frozen seed."""
    for db_path in (initial_db, after_db):
        tables = {r["name"] for r in db_query(
            db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(TABLES):
            raise ValueError(f"unexpected tables in {db_path}: {sorted(tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed_hash = schema_sha256(initial_db)
    if observed_hash != SCHEMA_SHA256:
        raise ValueError(f"unsupported landwatch schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["name"])
             for r in db_query(initial_db, "SELECT id, name, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    if users["alice.j@test.com"][0] != 1 or \
            db_query(initial_db, "SELECT password_hash FROM users WHERE email='alice.j@test.com'")[0][0] \
            != stable_password_hash(DEMO_PASSWORD):
        raise ValueError("benchmark user password hashes differ from the frozen seed")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen landwatch seed: rows digest {digest}")
    # benchmark users keep their identity columns in the after snapshot
    after_users = {r["email"]: (int(r["id"]), r["name"])
                   for r in db_query(after_db, "SELECT id, name, email FROM users")}
    if any(after_users.get(email) != ident for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) landwatch database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- landwatch-specific state helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def favorites_of(db_path, user_id):
    """[(pid, created_at)] favorites rows of one user, ordered by pid."""
    return sorted((int(r["pid"]), r["created_at"]) for r in db_query(
        db_path, "SELECT pid, created_at FROM favorites WHERE user_id = ?", (user_id,)))


def saved_searches_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM saved_searches WHERE user_id = ? ORDER BY id", (user_id,))]


def inquiries_rows(db_path):
    return [dict(r) for r in db_query(db_path, "SELECT * FROM inquiries ORDER BY id")]


def listing_by_pid(db_path, pid):
    rows = db_query(db_path, "SELECT * FROM listings WHERE pid = ? LIMIT 1", (int(pid),))
    return dict(rows[0]) if rows else None


def agent_by_id(db_path, account_id):
    rows = db_query(db_path, "SELECT * FROM agents WHERE account_id = ? LIMIT 1", (int(account_id),))
    return dict(rows[0]) if rows else None


def sessions_tokens(db_path):
    return sorted(str(r["token"]) for r in db_query(db_path, "SELECT token FROM sessions"))


def expected_session_token(user_id, user_email):
    """Deterministic session token the mirror derives from the user identity."""
    return hashlib.sha256(
        f"{PASSWORD_NAMESPACE}:session:{int(user_id)}:{user_email}".encode("utf-8")).hexdigest()


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
    judge.check("visited_login_page", navigated_to_path(traj, "/log-in"),
                "required_path=/log-in")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email),
                f"expected {email!r} in an input step; observed_inputs={input_texts(traj)!r}")


def check_visited_path(judge, traj, name, path):
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_read_only(judge, initial_db, after_db):
    changed = changed_tables(initial_db, after_db)
    return judge.check("read_only_db_unchanged", not changed, f"changed_tables={changed!r}")


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    """Every table outside `allowed` is row-identical before/after."""
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


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
        from reviewed import review
        review(judge, traj, initial_db, after_db, run_checks)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()
