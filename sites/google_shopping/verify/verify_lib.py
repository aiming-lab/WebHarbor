#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for
Google Shopping task verification.

Philosophy: DETERMINISTIC FIRST — same contract as ``sites/merriam_webster/verify/verify_lib.py``
hardened the way ``sites/chess_com/verify/verify_lib.py`` is (that file is the direct
structural reference for this one).

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty final
     answer, every recorded URL on the same loopback origin AND port as ``start_url``,
     every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the on-site
     surfaces the task names (homepage feed sections, departments grid, scored search with
     filters/sorts, product panels, deals, sign-in, shopping list, price tracking, account).
     A correct answer with no matching navigation is a memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / number / money / percent matching against
     frozen ground truth that is HARDCODED in each ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only tasks
     require every table row-identical; stateful tasks require the exact allowed row delta
     and nothing else (saved_items / tracked_products rows, one registered user).
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

SITE = "google_shopping"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("departments", "feed_sections", "merchants", "offers", "products", "reviews",
          "saved_items", "tracked_products", "users")
SEED_COUNTS = {"departments": 15, "feed_sections": 2, "merchants": 37, "offers": 61,
               "products": 61, "reviews": 0, "saved_items": 1, "tracked_products": 0,
               "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/google_shopping.db.
SCHEMA_SHA256 = "1d01ed2b4f8ec450350a1e79bc8db5723854f6f80dea9f45d79f221ea0808236"
# sha256 over every seed row (table-scanonical, ORDER BY all columns). The seed is rebuilt
# deterministically at image-build time (PYTHONHASHSEED=0, frozen bcrypt hash, see
# .build-generated-seed); the physical file layout may differ between sqlite builds but
# this logical digest is frozen.
SEED_ROWS_SHA256 = "bfd18c5b96ae208db485cac5d8c257aa6294bd819881783445987fbaae2b4ca0"
SEED_USERS = {  # email -> (id, display_name); identity columns never change
    "alice.j@test.com": (1, "Alice Johnson"),
    "bob.c@test.com": (2, "Bob Chen"),
    "carol.d@test.com": (3, "Carol Davis"),
    "david.k@test.com": (4, "David Kim"),
}
DEMO_PASSWORD = "TestPass123!"
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


def step_urls(traj):
    return [str(s.get("url", "")) for s in traj.get("steps", []) if isinstance(s, dict)]


def trajectory_urls(traj):
    """Every browser URL the recorder wrote: start_url, each step's url (+url_before/url_after), final_url."""
    urls: list[str] = []
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


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(str(name)).name)
    return p if (p and p.exists()) else None


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


def navigated_search_with(traj, must_tokens, exact_params=None, any_sort=None):
    """A /search visit whose query contains every `must_tokens` token (word-boundary,
    case-insensitive, hyphen/space equivalent) plus optional exact params (e.g.
    sort=price_asc) — used for the scored-search, filter and sort navigation gates."""
    wanted = {normalize_text(t) for t in must_tokens}
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        query = _query_params(u)
        q_values = " ".join(query.get("q", []))
        q_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(q_values)))
        if not wanted or wanted.issubset(q_tokens):
            ok = True
            for key, value in (exact_params or {}).items():
                if str(value) not in query.get(key, []):
                    ok = False
                    break
            if ok and (any_sort is None or any(v in query.get("sort", []) for v in any_sort)):
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
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


norm = normalize_text  # suite parity


def _match_is_affirmative(text, match):
    before = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()], flags=re.I)[-1]
    after = text[match.end():]
    return not re.search(r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|rather than)\b", before, re.I) \
        and not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|wrong|incorrect)\b", after, re.I)


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
    ('lunch box' == 'lunchbox' == 'lunch-box')."""
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


def contains_count(text, number):
    """`number` as a standalone integer (not inside a longer digit run, a decimal, a
    thousands group or an ordinal) or as its English word form."""
    normalized = normalize_text(text)
    n = int(number)
    pattern = rf"(?<![\d.,]){n}(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
    if _affirmative_search(pattern, normalized):
        return True
    word = _number_word(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def _money_candidates(amount):
    """Literal forms a correct agent may write for `amount`: '$129.90' == '$129.9',
    '$1704' == '$1,704.00' == '1704', '$50' == '$50.00'."""
    cents = round(float(amount) * 100)
    whole, rem = divmod(cents, 100)
    out = []
    if rem == 0:
        out += [str(whole), f"{whole}.00"]
        if whole >= 1000:
            s = str(whole)
            grouped = ""
            while len(s) > 3:
                grouped = "," + s[-3:] + grouped
                s = s[:-3]
            out.append(s + grouped)          # 1,704
            out.append((s + grouped).replace(",", " "))  # 1 704
    else:
        out.append(f"{whole}.{rem:02d}")
        if rem % 10 == 0:
            out.append(f"{whole}.{rem // 10}")  # 129.90 -> 129.9
    return out


def contains_price(text, amount):
    """Money match: '$129.90' == '$129.9' == '129.90 dollars'; '1704' == '1,704' == '1704.00'.
    Accepts an optional '$' and thousands separators; rejects the amount embedded in a
    longer digit run or a different decimal. Handles the mirror's whole-dollar display."""
    normalized = normalize_text(text)
    for candidate in _money_candidates(amount):
        pattern = r"(?<![\d.,])\$?\s?" + re.escape(candidate) + r"(?!\d|[.,]\d)"
        if _affirmative_search(pattern, normalized):
            return True
    return False


def contains_amount(text, number):
    """Backward-compatible alias with the other suites' semantics."""
    return contains_price(text, number)


def contains_percent(text, number):
    """'61%' / '61 percent' / '61 per cent' (affirmative)."""
    normalized = normalize_text(text)
    n = int(number)
    pattern = rf"(?<![\d.,]){n}(?!\d|[.,]\d)\s*(?:%|(?:per\s?cents?|percent)\b)"
    return _affirmative_search(pattern, normalized)


def contains_rating(text, rating):
    """'3.5' (or '3.5 stars') as the reported rating; '3.5' must not be part of a longer
    number. Also accepts '3.5/5'."""
    normalized = normalize_text(text)
    r = str(rating)
    pattern = rf"(?<![\d.,]){re.escape(r)}(?!\d|[.,]\d)"
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


def table_rows(db_path, table):
    return [tuple(row) for row in db_query(db_path, f"SELECT * FROM {table} ORDER BY id")]


def rows_by_id(db_path, table):
    return {int(row[0]): row for row in table_rows(db_path, table)}


def table_delta(initial_db, after_db, table):
    before, after = rows_by_id(initial_db, table), rows_by_id(after_db, table)
    return {
        "added": [after[i] for i in sorted(set(after) - set(before))],
        "removed": [before[i] for i in sorted(set(before) - set(after))],
        "changed": [(before[i], after[i]) for i in sorted(set(before) & set(after)) if before[i] != after[i]],
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
        cols = table_columns(db_path, table)
        order = ",".join(f"[{c}]" for c in cols)
        for row in db_query(db_path, f"SELECT {order} FROM [{table}] ORDER BY {order}"):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def validate_snapshot_contract(initial_db, after_db):
    """Raise ValueError unless both snapshots are genuine Google Shopping databases
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
        raise ValueError(f"unsupported google_shopping schema hash: {observed_hash}")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial database counts differ: expected={SEED_COUNTS}, observed={counts}")
    users = {r["email"]: (int(r["id"]), r["display_name"])
             for r in db_query(initial_db, "SELECT id, display_name, email FROM users")}
    observed = {email: ident for email, ident in users.items() if email in SEED_USERS}
    if observed != SEED_USERS:
        raise ValueError(f"initial benchmark users differ: {observed}")
    digest = rows_digest(initial_db)
    if digest != SEED_ROWS_SHA256:
        raise ValueError(f"initial database is not the frozen google_shopping seed: rows digest {digest}")
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
                    "both initial (seed) and after (instance) google_shopping database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def saved_pairs(db_path, user_id):
    """(user_id, product_id) rows currently in saved_items for one user."""
    return sorted((int(r["user_id"]), int(r["product_id"])) for r in db_query(
        db_path, "SELECT user_id, product_id FROM saved_items WHERE user_id = ?", (user_id,)))


def tracked_pairs(db_path, user_id):
    return sorted((int(r["user_id"]), int(r["product_id"])) for r in db_query(
        db_path, "SELECT user_id, product_id FROM tracked_products WHERE user_id = ?", (user_id,)))


def user_row_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


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


def check_signed_in_as(judge, traj, email, display_name):
    judge.check("visited_login_page", navigated_to_path(traj, "/login"),
                "required_path=/login (or /register for task 26)")
    judge.check("entered_expected_account_identity",
                entered_identity(traj, email, display_name),
                f"expected one of {email!r}/{display_name!r} in an input step; "
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
