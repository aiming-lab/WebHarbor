#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for Michaels task verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/marriott/verify/verify_lib.py``, ``sites/merriam_webster/verify/verify_lib.py``
and ``sites/jcpenney/verify/verify_lib.py``, the direct structural references for
this one). No LLM call is load-bearing; this suite is fully deterministic.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty
     final answer, every recorded URL on the same loopback origin AND port as
     ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — scored search (``/search?q=``), category
     listings (``/shop/<slug>`` with facet params), product pages (``/product/<slug>``)
     and their reviews tabs, the cart, the two-step checkout + confirmation, the
     account suite (orders / profile / addresses / payment / wishlist /
     registrations), the store locator, classes + registration, savings, coupon
     policy, rewards, login and register. A correct answer with no matching
     navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / date matching
     against frozen ground truth that is HARDCODED in each ``verify_N.py`` (never
     in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only
     tasks require every table row-identical; stateful tasks require the exact
     allowed row delta and nothing else (the added order row with its subtotal /
     discount / shipping / tax / total / promo / card / address, its order_items,
     cart_items add/remove/qty changes, wishlist deltas, a class registration row,
     a payment-method row, a created user row, a profile-phone update, an added
     address row). Order numbers are deterministic given the frozen seed and the
     pinned reference date (MI<YYMMDD><user_id:02d><seq:03d>) and must appear
     verbatim in the agent's final answer AND identify the added order row.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-michaels-review)
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

SITE = "michaels"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-michaels-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("users", "categories", "stores", "coupons", "classes", "addresses",
          "payment_cards", "products", "product_variants", "reviews", "questions",
          "cart_items", "wishlist_items", "orders", "order_items",
          "class_registrations")
SEED_COUNTS = {"users": 4, "categories": 74, "stores": 51, "coupons": 10,
               "classes": 37, "addresses": 5, "payment_cards": 5, "products": 347,
               "product_variants": 881, "reviews": 296, "questions": 95,
               "cart_items": 11, "wishlist_items": 14, "orders": 5,
               "order_items": 7, "class_registrations": 0}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/michaels.db.
SCHEMA_SHA256 = "c725a70cc8d41d50225f3ab0989e92b5ae92749a980a83d9a724bca59bd935c0"
# sha256 over every seed row (table-canonical, ORDER BY all columns). The seed ships
# in-repo (instance_seed/michaels.db, md5 0b2b1c21ec9afbd35a477175fa5712dd) and a
# clean in-container rebuild reproduces it byte-for-byte (PYTHONHASHSEED=0,
# MIRROR_REFERENCE_DATE-pinned order numbers).
SEED_ROWS_SHA256 = "26010fcb1fef37fa0bf055014e09730a210f235490e21a5e740a986b1de8c66e"
SEED_USERS = {  # email -> (id, name, phone); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson", "(206) 555-0183"),
    "bob.c@test.com": (2, "Bob Chen", "(206) 555-0183"),
    "carol.d@test.com": (3, "Carol Davis", "(206) 555-0183"),
    "david.k@test.com": (4, "David Kim", "(206) 555-0183"),
}
DEMO_PASSWORD = "TestPass123!"
INPUT_ACTIONS = {"input", "type", "fill", "input_text", "type_text"}
ORDER_NUMBER_RE = re.compile(r"\bMI\d{11}\b")


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


def navigated_search(traj, query_token, params=None):
    """/search visit whose q carries query_token (word-boundary tolerant) and whose
    query carries the exact key/value pairs (e.g. sort=price_low)."""
    token = normalize_text(query_token)
    wanted = {k: normalize_text(v) for k, v in (params or {}).items()}
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        query = _query_params(u)
        q = normalize_text(" ".join(query.get("q") or []))
        if token.split()[0] not in q:
            continue
        if all(str(value) in [normalize_text(v) for v in query.get(key, [])]
               for key, value in wanted.items()):
            return True
    return False


def navigated_shop(traj, slug, params=None):
    """/shop/<slug> visit with optional exact query params (sub, availability, sort)."""
    wanted = {k: normalize_text(v) for k, v in (params or {}).items()}
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if not path.startswith(f"/shop/{slug}"):
            continue
        if path != f"/shop/{slug}":
            continue
        query = _query_params(u)
        if all(str(value) in [normalize_text(v) for v in query.get(key, [])]
               for key, value in wanted.items()):
            return True
    return False


def navigated_product(traj, slug):
    """A /product/<slug> visit (reviews suffix tolerated on the same slug)."""
    return any(normalized_url_path(u) in (f"/product/{slug}", f"/product/{slug}/reviews")
               for u in site_urls(traj))


def navigated_product_reviews(traj, slug):
    return any(normalized_url_path(u) == f"/product/{slug}/reviews" for u in site_urls(traj))


def navigated_confirmation(traj, order_number=None):
    if order_number is None:
        return any(normalized_url_path(u).startswith("/order/confirmation/")
                   for u in site_urls(traj))
    return navigated_to_path(traj, f"/order/confirmation/{order_number}")


def navigated_account_order(traj, order_number):
    return navigated_to_path(traj, f"/account/order/{order_number}")


def navigated_store_locator_query(traj, token):
    """A /store-locator visit whose q carries token."""
    t = normalize_text(token)
    for u in site_urls(traj):
        if normalized_url_path(u) != "/store-locator":
            continue
        if t in normalize_text(" ".join(_query_params(u).get("q") or [])):
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


def entered_text_containing(traj, fragment):
    frag = normalize_text(fragment)
    return any(frag in normalize_text(v) for v in input_texts(traj))


def order_numbers_in_answer(answer):
    return ORDER_NUMBER_RE.findall(answer or "")


# ---------------------------------------------------------------- deterministic answer match
def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = (text.replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "-").replace("\u2026", "...")
            .replace("\u00a0", " "))
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text

_NEGATION_WORDS = r"(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|doesn't|dont|doesn|don't|aren't|arent|cannot|can't|cant)"


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
    """Phrase tokens with edge punctuation (commas etc.) stripped — product names on
    the mirror render with commas and the agent's answer may keep or drop them."""
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


_COUNT_WORDS = {"four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
                "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30}


def wrong_amount_claim_absent(text, expected, anchors=("discount", "bogo")):
    """No '<anchor> [amount|of|was|is|:|-] $X' claim with X != expected.

    Hardens amount-report checks against answers that state the WRONG amount
    while the expected figure happens to appear elsewhere in the text (e.g. the
    BOGO discount equals the cheaper item's price, which the answer also
    quotes). Percentages and promo-code digits are not amount claims.
    """
    normalized = normalize_text(text)
    anchor_re = "|".join(re.escape(a) for a in anchors)
    pattern = (rf"\b(?:{anchor_re})\s+(?:amount\s+|rate\s+)?(?:was|is|of|to|:|-)?\s*"
                rf"\$?\s*([\d][\d,]*(?:\.\d+)?)(?![\d%])")
    quantized = round(float(expected), 2)
    for m in re.finditer(pattern, normalized):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if abs(round(value, 2) - quantized) > 0.005:
            return False
    return True


def wrong_count_claim_absent(text, expected, anchors=("wishlist", "wish list", "it now")):
    """No present-tense '<anchor> ... shows/holds/has/is <N>' claim with N != expected.

    Hardens count-report checks against answers that state the WRONG current
    count while the correct number happens to appear elsewhere in the text
    (e.g. 'removed the three canvas items ... the wishlist now shows 4 items').
    Past-tense/earlier-state mentions (previously/before/earlier/used to/was/
    were/had/started/began) are excluded so honest before/after phrasings pass.
    """
    normalized = normalize_text(text)
    anchor_re = "|".join(re.escape(a) for a in anchors)
    tempered = (r"(?:(?!(?:previously|before|earlier|used to|was|were|had|originally|"
                r"initially|start(?:ed|s)?|began)\b)[^.!?]){0,40}?")
    pattern = (rf"(?:{anchor_re})" + tempered
               + r"\b(?:shows?|holds?|has|contains?|displays?|is|stands at)\s+"
                 r"(?:now\s+)?(\d+|" + "|".join(_COUNT_WORDS) + r")\b")
    for m in re.finditer(pattern, normalized):
        token = m.group(1)
        value = int(token) if token.isdigit() else _COUNT_WORDS[token]
        if value != int(expected):
            return False
    return True


_WIN_VERBS = r"(?:gives?|is|has|offers?|provides?|delivers?|comes to|wins?|beats?)"
_WIN_WORDS = r"(?:more|better|higher|greater|best)"


def winner_named(text, winner, loser):
    """Comparative-choice report hardening: the winner must be tied to a
    comparative claim (subject form 'the <winner> gives more ...' or
    reversed form 'more ... : the <winner>' / 'the winner is the <winner>'),
    and the loser must not be the subject of a direct present-tense win-claim
    ('the <loser> gives more ...', 'the <loser> wins').

    An incidental mention of the winner elsewhere in the answer no longer
    satisfies the report, and a plainly false winner claim now fails.
    """
    normalized = normalize_text(text)
    win = re.escape(normalize_text(winner))
    lose = re.escape(normalize_text(loser))
    # positive: winner tied to a comparative claim
    subject = re.search(rf"(?<!\w){win}(?!\w)\s+{_WIN_VERBS}\s+"
                        rf"(?:a|an|the|its|their)?\s*(?:\w+\s+){{0,1}}?{_WIN_WORDS}\b",
                        normalized)
    reversed_form = re.search(rf"\b(?:{_WIN_WORDS}|winner)\b[^.!?]{{0,40}}"
                               rf"(?<!\w){win}(?!\w)", normalized)
    wins_plain = re.search(rf"(?<!\w){win}(?!\w)[^.!?]{{0,20}}\b(?:wins?|winner)\b",
                            normalized)
    positive = bool(subject or reversed_form or wins_plain)
    # negative: direct false claim with the loser as the subject
    loser_claim = re.search(rf"(?<!\w){lose}(?!\w)\s+{_WIN_VERBS}\s+"
                            rf"(?:a|an|the|its|their)?\s*(?:\w+\s+){{0,1}}?{_WIN_WORDS}\b",
                            normalized)
    loser_wins = re.search(rf"(?<!\w){lose}(?!\w)[^.!?]{{0,20}}\b(?:wins?|winner)\b",
                            normalized)
    return positive and not loser_claim and not loser_wins


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
    """'September 28, 2026' == 'September 28 2026' == 'Sep. 28, 2026' (month-name tolerant)."""
    normalized = normalize_text(text)
    words = normalize_text(phrase).split()
    if len(words) != 3:
        return contains_phrase(text, phrase)
    month, day, year = words
    month_alts = {"january": "jan(?:uary)?", "february": "feb(?:ruary)?", "march": "mar(?:ch)?",
                  "april": "apr(?:il)?", "may": "may", "june": "jun(?:e)?", "july": "jul(?:y)?",
                  "august": "aug(?:ust)?", "september": "sep(?:t)?(?:ember)?",
                  "october": "oct(?:ober)?", "november": "nov(?:ember)?",
                  "december": "dec(?:ember)?", "sept": "sep(?:t)?(?:ember)?"}.get(month, month)
    day_bare = str(int(day.rstrip(",")))
    pattern = rf"\b{month_alts}\.?\s+0*{re.escape(day_bare)}\s*,?\s+{re.escape(year)}\b"
    return _affirmative_search(pattern, normalized)


def contains_slash_date(text, mm, dd, yyyy):
    """'09/28/2026' date form."""
    pattern = rf"(?<![\d/]){re.escape(str(mm).zfill(2))}/{re.escape(str(dd).zfill(2))}/{re.escape(str(yyyy))}(?![\d/])"
    return _affirmative_search(pattern, normalize_text(text))


def contains_time(text, hour, minute, ampm):
    """'3:00 pm' == '03:00 pm' == '3 pm' (minute-optional)."""
    h = re.escape(str(int(hour)))
    pattern = rf"\b0*{h}(?::\s*{re.escape(str(minute).zfill(2))})?\s*{re.escape(ampm.lower())}\b"
    return _affirmative_search(pattern, normalize_text(text))


def answer_is_negative(text, token):
    """The token appears only in a negated context (for 'can she stack...?' -> No)."""
    normalized = normalize_text(text)
    for m in re.finditer(r"(?<!\w)" + re.escape(normalize_text(token)) + r"(?!\w)", normalized):
        if _match_is_affirmative(normalized, m):
            return False
    return True


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
    """Raise ValueError unless both snapshots are genuine michaels databases derived
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
        raise ValueError(f"unsupported michaels schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["name"], r["phone"])
             for r in db_query(initial_db, "SELECT id, name, phone, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen michaels seed: rows digest {digest}")
    after_users = {r["email"]: (int(r["id"]), r["name"])
                   for r in db_query(after_db, "SELECT id, name, email FROM users")}
    if any(after_users.get(email) and after_users[email] != (ident[0], ident[1])
           for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) michaels database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- michaels-specific helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def product_by_slug(db_path, slug):
    rows = db_query(db_path, "SELECT * FROM products WHERE slug = ? LIMIT 1", (slug,))
    return dict(rows[0]) if rows else None


def orders_of(db_path, email=None):
    if email:
        return [dict(r) for r in db_query(db_path,
            "SELECT o.* FROM orders o JOIN users u ON o.user_id = u.id "
            "WHERE lower(u.email) = lower(?) ORDER BY o.id", (email,))]
    return [dict(r) for r in db_query(db_path, "SELECT * FROM orders ORDER BY id")]


def order_items_of(db_path, order_id):
    return [dict(r) for r in db_query(db_path,
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))]


def cart_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT c.* FROM cart_items c JOIN users u ON c.user_id = u.id "
        "WHERE lower(u.email) = lower(?) ORDER BY c.id", (email,))]


def wishlist_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT w.* FROM wishlist_items w JOIN users u ON w.user_id = u.id "
        "WHERE lower(u.email) = lower(?) ORDER BY w.id", (email,))]


def cards_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT p.* FROM payment_cards p JOIN users u ON p.user_id = u.id "
        "WHERE lower(u.email) = lower(?) ORDER BY p.id", (email,))]


def registrations_of(db_path, email):
    return [dict(r) for r in db_query(db_path,
        "SELECT r.* FROM class_registrations r JOIN users u ON r.user_id = u.id "
        "WHERE lower(u.email) = lower(?) ORDER BY r.id", (email,))]


def added_order_matching(after_db, initial_db, **expected):
    """The one order row added vs the seed whose fixed columns match `expected`
    (user, subtotal, discount, shipping, tax, total, promo_code, delivery_method,
    card_brand, card_last4, address_line...). Returns the full row or None."""
    initial_ids = {r["id"] for r in orders_of(initial_db)}
    added = [r for r in orders_of(after_db) if r["id"] not in initial_ids]
    for r in added:
        row = dict(r)
        if all(row.get(k) == v for k, v in expected.items()):
            return row
    return None


def added_cart_items_matching(after_db, initial_db, **expected):
    """Cart rows added vs the seed whose fixed columns match `expected`
    (user_id, product_id, variant_sku, color, qty). Returns all matching rows."""
    uid = expected.get("user_id")
    initial = {(r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
               for r in cart_of_raw(initial_db)}
    added = []
    for r in cart_of_raw(after_db):
        key = (r["user_id"], r["product_id"], r["variant_sku"], r["color"], r["qty"])
        if key in initial:
            continue
        if all(r.get(k) == v for k, v in expected.items()):
            added.append(dict(r))
    return added


def cart_of_raw(db_path):
    return [dict(r) for r in db_query(db_path, "SELECT * FROM cart_items ORDER BY id")]


def cart_qty_change(after_db, initial_db, user_id, product_id, variant_sku):
    """(before_qty, after_qty) for one cart row identified by (user, product, sku)."""
    def qty(db):
        rows = db_query(db, "SELECT qty FROM cart_items WHERE user_id = ? AND product_id = ? "
                            "AND variant_sku = ?", (user_id, product_id, variant_sku))
        return [r["qty"] for r in rows]
    before, after = qty(initial_db), qty(after_db)
    if not before or not after:
        return None
    return before[0], after[0]


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
    judge.check("visited_signin_page", navigated_to_path(traj, "/login"),
                "required_path=/login")
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


def check_answer_order_matches_added_order(judge, answer, added_row, label):
    """The deterministic order number reported in the answer must be the one on the
    added order row."""
    numbers = order_numbers_in_answer(answer)
    judge.check(f"{label}_order_number_in_answer",
                bool(added_row) and added_row["order_number"] in numbers,
                f"answer_orders={numbers!r}, added_row_order={added_row and added_row['order_number']!r}")
    return bool(added_row) and added_row["order_number"] in numbers


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
