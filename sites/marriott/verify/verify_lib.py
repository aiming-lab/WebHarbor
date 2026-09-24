#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for Marriott task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/merriam_webster/verify/verify_lib.py`` and ``sites/jcpenney/verify/verify_lib.py``,
the direct structural references for this one). No LLM call is load-bearing; this
suite is fully deterministic.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty
     final answer, every recorded URL on the same loopback origin AND port as
     ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the scored destination search
     (``/search/findHotels.mi`` with its exposed facets: brand / max price / guest
     rating / amenity / sort / points toggle and stay window), destination pages,
     hotel overview / rooms / reviews / photos tabs, the availability search, the
     reservation gateway + confirmation, the reservation lookup + cancel flow, and
     the Marriott Bonvoy account surfaces (account, profile, payment methods,
     saved hotels, registration). A correct answer with no matching navigation is
     a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / date matching
     against frozen ground truth that is HARDCODED in each ``verify_N.py`` (never
     in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only
     tasks require every table row-identical; stateful tasks require the exact
     allowed row delta and nothing else (one reservation row with the task's
     hotel / room / dates / guest / total — the confirmation number itself is
     runtime-random and is instead required to appear verbatim in the agent's
     final answer AND to identify the added row; a reservation status flip to
     ``canceled``; a points debit; user profile fields; payment-method add/remove;
     favorite add/remove; a newly registered user).
  5. ``--no_llm`` exists for CLI parity with the sibling suites; there are no LLM
     checks here, so it changes nothing.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-marriott-review)
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

SITE = "marriott"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-marriott-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("brands", "destinations", "favorites", "hotel_images", "hotels", "offers",
          "payment_methods", "reservations", "reviews", "room_types", "users")
SEED_COUNTS = {"brands": 31, "destinations": 20, "favorites": 12, "hotel_images": 2436,
               "hotels": 235, "offers": 8, "payment_methods": 4, "reservations": 11,
               "reviews": 6538, "room_types": 1175, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/marriott.db.
SCHEMA_SHA256 = "718698ab6a0b73efefe6c3d769171cf1ec5ffcd9e9be117bab4019603ff93898"
# sha256 over every seed row (table-canonical, ORDER BY all columns). The seed is
# rebuilt deterministically at image-build time (PYTHONHASHSEED=0, frozen bcrypt
# digest, MIRROR_REFERENCE_DATE-pinned fixture dates — see .build-generated-seed);
# a clean in-container rebuild reproduces the shipped seed byte-for-byte
# (md5 9d60b205d4efeaf5969ad0e45748adb3).
SEED_ROWS_SHA256 = "b0cc7deb5d9c41ce7914e36a3ce56e68bdbbfe0b1c0d6225a7f936f6a9b4c146"
SEED_USERS = {  # email -> (id, first_name, last_name); identity columns never change
    "alice.j@test.com": (1, "Alice", "Johnson"),
    "bob.c@test.com": (2, "Bob", "Chen"),
    "carol.d@test.com": (3, "Carol", "Davis"),
    "david.k@test.com": (4, "David", "Kim"),
}
DEMO_PASSWORD = "TestPass123!"
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}
CONFIRMATION_RE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]{10}\b")


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
            parse_qs(urlparse(str(url)).query, keep_blank_values=True).items()}


def navigated_to(traj, substr, times=1):
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def navigated_find_hotels(traj, dest_token, params=None):
    """/search/findHotels.mi visit whose destinationAddress carries dest_token and
    whose query carries the exact key/value pairs (e.g. minRating=4, sortBy=price,
    amenity=Pool, useRewardsPoints=true)."""
    token = normalize_text(dest_token)
    wanted = {k: normalize_text(v) for k, v in (params or {}).items()}
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search/findHotels.mi":
            continue
        query = _query_params(u)
        dest = normalize_text(" ".join(query.get("destinationAddress") or []))
        if token not in dest:
            continue
        if all(str(value) in [normalize_text(v) for v in query.get(key, [])]
               for key, value in wanted.items()):
            return True
    return False


def navigated_find_hotels_dest(traj, *dest_tokens):
    tokens = [normalize_text(t) for t in dest_tokens]
    return any(normalized_url_path(u) == "/search/findHotels.mi"
               and any(t in normalize_text(" ".join(_query_params(u).get("destinationAddress") or []))
                       for t in tokens)
               for u in site_urls(traj))


def navigated_availability(traj, marsha):
    """/reservation/availabilitySearch.mi?propertyCode=<marsha> visit."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/reservation/availabilitySearch.mi":
            continue
        codes = [c.upper() for c in _query_params(u).get("propertyCode", [])]
        if marsha.upper() in codes:
            return True
    return False


def navigated_gateway(traj, marsha=None, with_room=False):
    urls = [u for u in site_urls(traj) if normalized_url_path(u) == "/reservation/reservationGateway.mi"]
    if not urls:
        return False
    if marsha is None and not with_room:
        return True
    for u in urls:
        query = _query_params(u)
        if marsha is not None and marsha.upper() not in [c.upper() for c in query.get("propertyCode", [])]:
            continue
        if with_room and not query.get("roomId"):
            continue
        return True
    return False


def navigated_confirmation(traj):
    return navigated_to_path(traj, "/reservation/confirmation.mi")


def navigated_hotel_tab(traj, tab, hotel_slug=None):
    """/en-us/hotels/<slug>/<tab>/ visit (trailing slash tolerated on both sides)."""
    raw_suffix = f"/{tab}/"
    bare_suffix = f"/{tab}"
    for u in site_urls(traj):
        raw_path = urlparse(str(u)).path or "/"
        path = raw_path.rstrip("/") or "/"
        if hotel_slug and hotel_slug not in path:
            continue
        if not path.startswith("/en-us/hotels/"):
            continue
        if raw_path.endswith(raw_suffix) or path.endswith(bare_suffix):
            return True
    return False


def navigated_hotel_overview(traj, hotel_slug=None):
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if hotel_slug and hotel_slug not in path:
            continue
        if path.startswith("/en-us/hotels/") and path.rstrip("/").endswith("/overview"):
            return True
        if hotel_slug and path.startswith(f"/en-us/hotels/{hotel_slug}"):
            return True
    return False


def navigated_destination_page(traj, city_slug):
    return any(normalized_url_path(u).startswith(f"/en-us/destinations/")
               and city_slug in normalized_url_path(u) for u in site_urls(traj))


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


def entered_text_containing(traj, fragment):
    frag = normalize_text(fragment)
    return any(frag in normalize_text(v) for v in input_texts(traj))


def conf_numbers_in_answer(answer):
    return CONFIRMATION_RE.findall(answer or "")


# ---------------------------------------------------------------- deterministic answer match
def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = (text.replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "-").replace("\u2026", "..."))
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text

_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|doesn't|dont|doesn|don't|aren't|arent)"


def _match_is_affirmative(text, match):
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


def _phrase_words(phrase):
    """Phrase tokens with edge punctuation (commas etc.) stripped — hotel names on
    the mirror render with commas ('The ENGLiSH Hotel, Las Vegas, a Tribute Portfolio
    Hotel') and the agent's answer may keep or drop them."""
    return [re.escape(w.strip(",;:.")) for w in
            normalize_text(phrase).replace("-", " ").replace("_", " ").split() if w.strip(",;:.")]


def contains_phrase(text, phrase):
    words = _phrase_words(phrase)
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_,=:\-]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def phrases_in_order(text, phrases):
    normalized = normalize_text(text)
    cursor = 0
    for phrase in phrases:
        words = _phrase_words(phrase)
        if not words:
            return False
        pattern = r"(?<!\w)" + r"[\s_,=:\-]*".join(words) + r"(?!\w)"
        m = re.search(pattern, normalized[cursor:])
        if not m or not _match_is_affirmative(normalized[cursor:], m):
            return False
        cursor += m.end()
    return True


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}


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
    if n in _NUMBER_WORDS:
        return _affirmative_search(rf"\b{_NUMBER_WORDS[n]}\b", normalized)
    return False


def contains_amount(text, value):
    """Money amount: '$63' == '63' == '$63.00' == '63.00'; '$1,160' == '1160' ==
    '1,160' (every digit form tried, so comma-grouped page renderings match)."""
    normalized = normalize_text(text)
    quantized = round(float(value), 2)
    if quantized == int(quantized):
        for whole in _digit_forms(int(quantized)):
            pattern = r"(?<![\d.,])\$?\s?" + whole + r"(?:\.0+)?(?![\d]|\.\d)"
            if _affirmative_search(pattern, normalized):
                return True
        return False
    rendered = f"{quantized:.2f}"
    whole, dec = rendered.split(".")
    if dec.endswith("0"):
        dec_alt = dec.rstrip("0")
        dec_pattern = rf"{re.escape(dec)}|{re.escape(dec_alt)}"
    else:
        dec_pattern = re.escape(dec)
    pattern = rf"(?<![\d.,])\$?\s?{re.escape(whole)}\.(?:{dec_pattern})(?![\d])"
    return _affirmative_search(pattern, normalized)


def contains_date_phrase(text, phrase):
    """'November 2, 2026' == 'November 2 2026' == 'Nov. 2, 2026' (month-name tolerant)."""
    normalized = normalize_text(text)
    words = normalize_text(phrase).split()
    if len(words) != 3:
        return contains_phrase(text, phrase)
    month, day, year = words
    month_alts = {"january": "jan(?:uary)?", "february": "feb(?:ruary)?", "march": "mar(?:ch)?",
                  "april": "apr(?:il)?", "may": "may", "june": "jun(?:e)?", "july": "jul(?:y)?",
                  "august": "aug(?:ust)?", "september": "sep(?:t)?(?:ember)?",
                  "october": "oct(?:ober)?", "november": "nov(?:ember)?",
                  "december": "dec(?:ember)?"}.get(month, month)
    day_bare = str(int(day.rstrip(",")))  # tolerate zero-padded days ("Nov 02, 2026")
    pattern = rf"\b{month_alts}\.?\s+0*{re.escape(day_bare)}\s*,?\s+{re.escape(year)}\b"
    return _affirmative_search(pattern, normalized)


def contains_slash_date(text, mm, dd, yyyy):
    """'11/06/2026' date form."""
    pattern = rf"(?<![\d/]){re.escape(str(mm).zfill(2))}/{re.escape(str(dd).zfill(2))}/{re.escape(str(yyyy))}(?![\d/])"
    return _affirmative_search(pattern, normalize_text(text))


def contains_time(text, hour, minute, ampm):
    """'4:00 pm' == '4:00pm' == '4 pm' (minute-optional)."""
    h = re.escape(str(hour))
    pattern = rf"\b{h}(?::\s*{re.escape(str(minute).zfill(2))})?\s*{re.escape(ampm.lower())}\b"
    return _affirmative_search(pattern, normalize_text(text))


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
    order = _order_clause(db_path, table)
    return [tuple(row) for row in db_query(db_path, f"SELECT {order} FROM [{table}] ORDER BY {order}")]


def rows_by_pk(db_path, table):
    cols = table_columns(db_path, table)
    rows = table_rows(db_path, table)
    return {tuple(row[:1]): row for row in rows}, cols


def table_delta(initial_db, after_db, table):
    before, _ = rows_by_pk(initial_db, table)
    after, _ = rows_by_pk(after_db, table)
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
    """Raise ValueError unless both snapshots are genuine marriott databases derived
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
        raise ValueError(f"unsupported marriott schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["first_name"], r["last_name"])
             for r in db_query(initial_db, "SELECT id, first_name, last_name, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen marriott seed: rows digest {digest}")
    after_users = {r["email"]: (int(r["id"]), r["first_name"], r["last_name"])
                   for r in db_query(after_db, "SELECT id, first_name, last_name, email FROM users")}
    if any(after_users.get(email) and after_users[email] != ident
           for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) marriott database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- marriott-specific helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def hotel_by_name(db_path, name):
    rows = db_query(db_path, "SELECT * FROM hotels WHERE name = ? LIMIT 1", (name,))
    return dict(rows[0]) if rows else None


def reservation_rows(db_path, sql, params=()):
    return [dict(r) for r in db_query(db_path, sql, params)]


def reservations_of(db_path, email=None):
    if email:
        return reservation_rows(db_path,
            "SELECT r.* FROM reservations r JOIN users u ON r.user_id = u.id "
            "WHERE lower(u.email) = lower(?) ORDER BY r.id", (email,))
    return reservation_rows(db_path, "SELECT * FROM reservations ORDER BY id")


def reservation_snapshot(rows):
    """Comparable projection of reservation rows (drops runtime-random/irrelevant cols)."""
    keys = ("hotel_id", "room_type_id", "guest_first_name", "guest_last_name", "guest_email",
            "checkin", "checkout", "nightly_rate", "total_rate", "points_redeemed", "status",
            "adults", "rooms", "user_id")
    return [{k: r.get(k) for k in keys} for r in rows]


def favorites_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT f.id, f.saved_on, h.name AS hotel_name, h.city FROM favorites f "
        "JOIN users u ON f.user_id = u.id JOIN hotels h ON f.hotel_id = h.id "
        "WHERE lower(u.email) = lower(?) ORDER BY f.saved_on DESC, f.id", (email,))]


def payments_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT p.* FROM payment_methods p JOIN users u ON p.user_id = u.id "
        "WHERE lower(u.email) = lower(?) ORDER BY p.id", (email,))]


def added_reservation_matching(after_db, initial_db, **expected):
    """The one reservation row added vs the seed whose fixed columns match `expected`
    (hotel name, room name, guest, dates, total...). Returns the full row or None."""
    initial_ids = {r["id"] for r in reservations_of(initial_db)}
    added = [r for r in reservations_of(after_db) if r["id"] not in initial_ids]
    for r in added:
        row = dict(r)
        row["hotel_name"] = hotel_by_name(after_db, "")  # placeholder replaced below
        del row["hotel_name"]
        hotel = db_query(after_db, "SELECT name FROM hotels WHERE id = ?", (r["hotel_id"],))
        room = db_query(after_db, "SELECT name FROM room_types WHERE id = ?", (r["room_type_id"],))
        if not hotel or not room:
            continue
        row["hotel_name"] = hotel[0]["name"]
        row["room_name"] = room[0]["name"]
        if all(row.get(k) == v for k, v in expected.items()):
            return row
    return None


def canceled_among(initial_db, after_db, conf_number):
    """conf_number's reservation: seed status confirmed, after status canceled."""
    seed_rows = {r["confirmation_number"]: r for r in reservations_of(initial_db)}
    after_rows = {r["confirmation_number"]: r for r in reservations_of(after_db)}
    seed, after = seed_rows.get(conf_number), after_rows.get(conf_number)
    if not seed or not after:
        return False
    return seed["status"] == "confirmed" and after["status"] == "canceled"


# ---------------------------------------------------------------- judge harness
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
    """The named demo account must have been entered on the sign-in page (the mirror
    authenticates by email; the password never needs to appear in the trajectory)."""
    judge.check("visited_signin_page", navigated_to_path(traj, "/sign-in.mi"),
                "required_path=/sign-in.mi")
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


def check_answer_conf_matches_added_reservation(judge, answer, added_row, label):
    """The runtime-random confirmation number reported in the answer must be the one
    on the added reservation row."""
    confs = conf_numbers_in_answer(answer)
    judge.check(f"{label}_conf_in_answer",
                bool(added_row) and added_row["confirmation_number"] in confs,
                f"answer_confs={confs!r}, added_row_conf={added_row and added_row['confirmation_number']!r}")
    return bool(added_row) and added_row["confirmation_number"] in confs


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
