#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for
macys_wine_shop task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/merriam_webster/verify/verify_lib.py``, ``sites/instructure/verify/verify_lib.py``):

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty final
     answer, every recorded URL on the same loopback origin AND port as ``start_url``,
     every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the on-site
     surfaces the task names (the scored site search with its sort menu, collection
     listings with their metafield facet filters and sort menu, product detail pages
     for bottles and pack cases, the cart, the three-step checkout, the account orders
     history, the Wine Club page, the Wine 101 blog articles, the gift-card product).
     A correct answer with no matching navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / number / money matching against frozen
     ground truth that is HARDCODED in each ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only tasks
     require every table row-identical; stateful tasks require the exact allowed row delta
     and nothing else (a guest cart row, a placed order with its items, a new user).
  5. LLM utilities are kept for parity with the other suites. They are anchored on ground
     truth, make one call each, and are NEVER load-bearing: every verdict is decided with
     ``--no_llm True`` and the helpers only add ``[INFO]`` evidence.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-rev-macys_wine_shop)
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
from urllib.parse import parse_qs, quote, unquote, urlparse

SITE = "macys_wine_shop"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-rev-macys_wine_shop")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("addresses", "blog_articles", "cart_items", "case_bottles", "collection_products",
          "collections", "home_sections", "newsletter_subscribers", "order_items", "orders",
          "payment_methods", "product_images", "product_variants", "products", "reviews",
          "site_texts", "state_disclosures", "static_pages", "users")
SEED_COUNTS = {"addresses": 5, "blog_articles": 87, "cart_items": 8, "case_bottles": 751,
              "collection_products": 3577, "collections": 201, "home_sections": 10,
              "newsletter_subscribers": 2, "order_items": 8, "orders": 8,
              "payment_methods": 5, "product_images": 412, "product_variants": 415,
              "products": 371, "reviews": 232, "site_texts": 12, "state_disclosures": 48,
              "static_pages": 12, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/macys_wine_shop.db.
SCHEMA_SHA256 = "7fdbd7fc391e707242d78b324fba5cde5b71c424b3591b5d3437c6c41f2ee95b"
# sha256 over every seed row (table-scanonical, ORDER BY all columns). The seed is rebuilt
# deterministically at image-build time (PYTHONHASHSEED=0, stable sha256 password hash, see
# .build-generated-seed); the physical file layout may differ between sqlite builds but
# this logical digest is frozen.
SEED_ROWS_SHA256 = "b39ecf94bdfc8cad1e4e50211ad6a5d1598fa386c8c6a57a5e455f0779ba7caf"
SEED_USERS = {  # email -> (id, username); identity columns never change
    "alice.j@test.com": (1, "alice_j"),
    "bob.c@test.com": (2, "bob_c"),
    "carol.d@test.com": (3, "carol_d"),
    "david.k@test.com": (4, "david_k"),
}
DEMO_PASSWORD = "TestPass123!"
# primary key columns per table (delta keys); default "id"
PK_COLUMNS = {}
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
    """Every browser URL the recorder wrote: start_url, each step's url (+url_before/url_after), final_url."""
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


def navigated_to(traj, substr, times=1):
    """At least `times` recorded on-site URLs contain substr."""
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


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


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def _query_params(url):
    return {k: [unquote(v) for v in vals] for k, vals in
            parse_qs(urlparse(str(url)).query, keep_blank_values=True).items()}


def navigated_to_path_with_params(traj, expected_path, params):
    """Some on-site URL whose path matches AND whose query carries the exact key/value
    pairs (value match is exact after URL-decoding)."""
    expected = normalized_url_path(expected_path)
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = _query_params(u)
        if all(str(value) in query.get(key, []) for key, value in params.items()):
            return True
    return False


def _facet_param(facet):
    """metafield-style facet parameter, e.g. varietal -> filter.p.m.drinks.varietal."""
    return f"filter.p.m.drinks.{facet}"


def navigated_collection_with_facets(traj, handle, facets):
    """A collection listing visit whose query applies every (facet, value) filter
    (e.g. {'varietal': 'Cabernet Sauvignon', 'country': 'Italy'})."""
    expected = normalized_url_path(f"/collections/{handle}")
    wanted = {_facet_param(f): normalize_text(v) for f, v in facets.items()}
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = _query_params(u)
        ok = True
        for key, value in wanted.items():
            values = [normalize_text(v) for v in query.get(key, [])]
            if value not in values and not any(value in v.split(",") for v in values):
                ok = False
                break
        if ok:
            return True
    return False


def navigated_listing_sorted(traj, path_prefix, sort):
    """A listing URL (path starts with path_prefix) carrying sort_by=<sort>."""
    prefix = normalized_url_path(path_prefix)
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if not (path == prefix or path.startswith(prefix)):
            continue
        if str(sort) in _query_params(u).get("sort_by", []):
            return True
    return False


def navigated_search_with(traj, param, must_tokens):
    """A /search visit whose `param` (q) query contains every `must_tokens` token
    (word-boundary, case-insensitive, hyphen/space equivalent)."""
    wanted = {normalize_text(t) for t in must_tokens}
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        query = _query_params(u)
        q_values = " ".join(query.get(param, []))
        q_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(q_values)))
        if wanted and wanted.issubset(q_tokens):
            return True
    return False


def search_queries(traj):
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == "/search":
            for q in _query_params(u).get("q") or _query_params(u).get("keys") or []:
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
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace("…", "...")
    # accent folding for product names captured with diacritics (Alquería, Montañero, Rosé)
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text


_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt)"


def _match_is_affirmative(text, match):
    # Negation window: a negation word invalidates the match only when it sits within
    # the last three words before it ("no percentage discount is shown" style sentences
    # are handled by the callers, which phrase expectations affirmatively).
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
    """Whole-word phrase match tolerant of hyphen/space/no-space joins
    ('per bottle' == 'perbottle' == 'per-bottle')."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def phrases_in_order(text, phrases):
    """Each phrase present (contains_phrase semantics) AND appearing left-to-right."""
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
    """'20967' == '20,967' == '20 967' (thousands-group tolerant)."""
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
    thousands group or an ordinal), tolerant of thousands separators, or as its English
    word form."""
    normalized = normalize_text(text)
    n = int(number)
    for form in _digit_forms(n):
        pattern = r"(?<![\d.,])" + form + r"(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
        if _affirmative_search(pattern, normalized):
            return True
    word = _number_word(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_money(text, amount):
    """A dollar amount: '$13.99' == '13.99' (the $ is optional but the exact two-decimal
    form is required; thousands groups tolerated)."""
    s = f"{float(amount):.2f}"
    grouped = ""
    tail = s
    while len(tail.split(".")[0]) > 3:
        grouped = "," + tail[-6:] + grouped
        tail = tail[:-3]
    forms = [re.escape(s)]
    intpart, dec = s.split(".")
    if len(intpart) > 3:
        grouped_int = f"{int(intpart):,}"
        forms.append(re.escape(f"{grouped_int}.{dec}"))
        forms.append(re.escape(f"{grouped_int}.{dec}").replace(r"\,", r"\s?"))
    normalized = normalize_text(text)
    for form in forms:
        pattern = r"(?<![\d.])\$?" + form + r"(?![\d])"
        if _affirmative_search(pattern, normalized):
            return True
    return False


def contains_percent(text, value):
    """'19%' == '19 %' == '19 percent'."""
    n = int(value)
    return (_affirmative_search(rf"(?<![\d.,]){n}\s?%(?![\d])", normalize_text(text))
            or _affirmative_search(rf"(?<![\d.,]){n}\s+percent(?![\w])", normalize_text(text)))


def contains_free(text):
    """'FREE' (all caps on the mirror cart) case-insensitively."""
    return _affirmative_search(r"\bfree\b", normalize_text(text))


# ---------------------------------------------------------------- DB state
def db_query(db_path, sql, params=()):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state). docker cp -> temp file."""
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
    """Table-scanonical digest over every row (ORDER BY all columns) — environment-independent."""
    h = hashlib.sha256()
    for table in tables:
        for row in table_rows(db_path, table):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def validate_snapshot_contract(initial_db, after_db):
    """Raise ValueError unless both snapshots are genuine macys_wine_shop databases derived
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
        raise ValueError(f"unsupported macys_wine_shop schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["username"])
             for r in db_query(initial_db, "SELECT id, username, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen macys_wine_shop seed: rows digest {digest}")
    # benchmark users keep their identity columns in the after snapshot
    after_users = {r["email"]: (int(r["id"]), r["username"])
                   for r in db_query(after_db, "SELECT id, username, email FROM users")}
    if any(after_users.get(email) and after_users[email] != ident
           for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) macys_wine_shop database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- macys-specific state helpers
def product_by_handle(db_path, handle):
    rows = db_query(db_path, "SELECT * FROM products WHERE handle = ? LIMIT 1", (handle,))
    return dict(rows[0]) if rows else None


def variant_of_product(db_path, handle, offset=0):
    rows = db_query(db_path,
                    "SELECT v.* FROM product_variants v JOIN products p ON p.id = v.product_id "
                    "WHERE p.handle = ? ORDER BY v.position, v.id", (handle,))
    if not rows or offset >= len(rows):
        return None
    return dict(rows[offset])


def cart_rows(db_path, user_id=None):
    """Cart rows for one owner: a benchmark user (user_id) or the guest session(s)
    (user_id IS NULL rows are attributed to the run's fresh session)."""
    if user_id is not None:
        return [dict(r) for r in db_query(
            db_path, "SELECT * FROM cart_items WHERE user_id = ? ORDER BY id", (user_id,))]
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM cart_items WHERE user_id IS NULL ORDER BY id")]


def orders_of(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM orders WHERE user_id = ? ORDER BY id", (user_id,))]


def order_items_of(db_path, order_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))]


def users_email_map(db_path):
    return {int(r["id"]): r["email"] for r in db_query(db_path, "SELECT id, email FROM users")}


def cart_bottles(rows):
    """Total bottle count of cart rows (a row's variant decides its bottle_count)."""
    return sum(int(r["quantity"]) * 1 for r in rows)  # quantity is per-bottle for Bottle rows;
    # pack rows carry quantity = case count, so callers pass explicit bottle math instead


def money(value):
    return f"${float(value):,.2f}"


# ---------------------------------------------------------------- judge harness
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = bool(no_llm)
        self.ok = True
        self.reason = ""
        self.evidence = []

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
        """Advisory evidence that never affects the verdict (used for the anchored LLM helpers)."""
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
    """The named demo account must have been entered on the sign-in page (the mirror
    authenticates by email; the password never needs to appear in the trajectory)."""
    judge.check("visited_signin_page", navigated_to_path(traj, "/login"),
                "required_path=/login")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email),
                f"expected {email!r} in an input step; "
                f"observed_inputs={input_texts(traj)!r}")


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


def guest_cart_bottle_math(db_path, rows):
    """Bottle count of guest cart rows, honoring each variant's bottle_count."""
    total = 0
    for r in rows:
        v = db_query(db_path, "SELECT bottle_count FROM product_variants WHERE id = ?",
                     (r["variant_id"],))
        bc = int(v[0]["bottle_count"]) if v else 1
        total += int(r["quantity"]) * bc
    return total


def guest_cart_subtotal(db_path, rows):
    total = 0.0
    for r in rows:
        v = db_query(db_path, "SELECT price FROM product_variants WHERE id = ?", (r["variant_id"],))
        total += int(r["quantity"]) * float(v[0]["price"] if v else 0)
    return round(total, 2)


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
