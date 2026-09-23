#!/usr/bin/env python3
"""verify_lib.py — shared deterministic (+ anchored, advisory-only LLM) utilities for Chess.com task verification.

Philosophy: DETERMINISTIC FIRST — same contract as ``sites/merriam_webster/verify/verify_lib.py``
hardened the way ``sites/9gag/verify/verify_lib.py`` is (that file is the direct structural
reference for this one).

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``, non-empty final answer,
     every recorded URL on the same loopback origin AND port as ``start_url``, every referenced
     screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the on-site pages the
     task names (leaderboards, member profile, news article, opening, lesson, puzzle archive/detail,
     club, games, events, search). A correct answer with no matching navigation is a memory-recall
     shortcut = FAIL.
  3. Answer check: affirmative token / number / phrase / amount / date matching against frozen
     ground truth that is HARDCODED in each ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots. Read-only tasks require
     every table row-identical; stateful tasks require the exact allowed row delta and nothing else.
  5. LLM utilities are kept for parity with the other suites. They are anchored on ground truth,
     make one call each, and are NEVER load-bearing: every verdict is decided with ``--no_llm True``
     and the helpers only add ``[INFO]`` evidence.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm True        skip the advisory LLM evidence (verdicts never depend on it)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
# NOTE: no `from __future__ import annotations` here — simpleArgParser reads the dataclass
# field types at runtime and needs real types, not strings.
import atexit
import base64
import hashlib
import hmac
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
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

SITE = "chess_com"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("bots", "chess_events", "club_memberships", "clubs", "follows",
          "leaderboard_entries", "leaderboard_stats", "lesson_courses", "lesson_progress",
          "master_games", "master_players", "news_articles", "opening_top_players", "openings",
          "player_ratings", "puzzle_attempts", "puzzles", "today_items", "tv_slots", "users")
SEED_COUNTS = {"bots": 217, "chess_events": 20, "club_memberships": 5, "clubs": 38, "follows": 10,
               "leaderboard_entries": 1300, "leaderboard_stats": 4, "lesson_courses": 25,
               "lesson_progress": 2, "master_games": 375, "master_players": 15, "news_articles": 192,
               "opening_top_players": 1203, "openings": 200, "player_ratings": 1898,
               "puzzle_attempts": 3, "puzzles": 625, "today_items": 4, "tv_slots": 72, "users": 1179}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/chess_com.db.
SCHEMA_SHA256 = "e4f507ee48467cea7d4b3aad0ae5d19eaaea644ae2778d4ce55221be30b745a3"
# sha256 over every seed row (table-scanonical, ORDER BY all columns). The seed is rebuilt
# deterministically at image-build time (PYTHONHASHSEED=0, see .build-generated-seed); the
# physical file layout may differ between sqlite builds but this logical digest is frozen.
SEED_ROWS_SHA256 = "8a80a039b34ff198e27d77f09e1693ae89f4cf8a625841825df264cb78ae4fe4"
SEED_USERS = {  # email -> (id, username); identity columns never change
    "alice.j@test.com": (1176, "alice_j"),
    "bob.c@test.com": (1177, "bob_c"),
    "carol.d@test.com": (1178, "carol_d"),
    "david.k@test.com": (1179, "david_k"),
}
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


def navigated_to_path_with_params(traj, expected_path, params):
    """Some on-site URL whose path matches AND whose query carries the exact key/value pairs."""
    expected = normalized_url_path(expected_path)
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = parse_qs(urlparse(u).query, keep_blank_values=True)
        if all(any(str(v) == str(value) for v in query.get(key) or []) for key, value in params.items()):
            return True
    return False


def navigated_to_path_with_any_param(traj, expected_path, key, values):
    """Path matches AND the query param `key` equals any of `values` (used for /lessons?category=X)."""
    expected = normalized_url_path(expected_path)
    wanted = {normalize_text(v) for v in values}
    for u in site_urls(traj):
        if normalized_url_path(u) != expected:
            continue
        query = parse_qs(urlparse(u).query, keep_blank_values=True)
        for v in query.get(key) or []:
            if normalize_text(v) in wanted:
                return True
    return False


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", normalize_text(text)))


def search_queries(traj):
    out = []
    for u in site_urls(traj):
        if normalized_url_path(u) == "/search":
            for q in parse_qs(urlparse(u).query, keep_blank_values=True).get("q") or []:
                out.append(q)
    return out


def search_visited(traj, tokens_any):
    """Some /search?q= visit whose query contains at least one of `tokens_any` as a whole token."""
    wanted = {normalize_text(t) for t in tokens_any}
    return any(_tokens(q) & wanted for q in search_queries(traj))


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


norm = normalize_text  # merriam parity


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
    """Whole-word phrase match tolerant of hyphen/space/no-space joins ('lunch box' == 'lunchbox' == 'lunch-box')."""
    words = [re.escape(w) for w in normalize_text(phrase).replace("-", " ").replace("_", " ").split()]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"
    return _affirmative_search(pattern, normalize_text(text))


def phrases_in_order(text, phrases):
    """Each phrase present (contains_phrase semantics) AND appearing left-to-right in the answer."""
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
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}


def contains_count(text, number):
    """`number` as a standalone integer (not inside a longer digit run, a decimal, a thousands
    group or an ordinal) or as its English word form."""
    normalized = normalize_text(text)
    n = int(number)
    pattern = rf"(?<![\d.,]){n}(?!\d|[.,]\d|\s*(?:st|nd|rd|th)\b)"
    if _affirmative_search(pattern, normalized):
        return True
    word = _NUMBER_WORDS.get(n)
    return bool(word and _affirmative_search(rf"\b{word}\b", normalized))


def contains_amount(text, number):
    """`number` as an integer or with thousands separators ('919742' == '919,742' == '919 742')."""
    normalized = normalize_text(text)
    n = str(int(number))
    # allow optional ','/' ' between every third digit group
    digits = list(n)
    parts = [re.escape(digits[0])]
    for i, d in enumerate(digits[1:], start=1):
        sep = r"[,\s]?" if (len(digits) - i) % 3 == 0 else ""
        parts.append(sep + re.escape(d))
    pattern = r"(?<![\d.,])" + "".join(parts) + r"(?!\d)"
    return _affirmative_search(pattern, normalized)


def contains_percent(text, number):
    """'61%' / '61 percent' / '61 per cent'."""
    normalized = normalize_text(text)
    n = int(number)
    pattern = rf"(?<![\d.,]){n}(?!\d|[.,]\d)\s*(?:%|(?:per\s?cents?|percent)\b)"
    return _affirmative_search(pattern, normalized)


_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
_MONTH_ABBR = {m[:3].lower(): i for m, i in _MONTHS.items()}


def contains_date(text, iso):
    """'2026-08-19' or 'Aug 19, 2026' or '19 August 2026' or 'August 19th, 2026' (all affirmative)."""
    normalized = normalize_text(text)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso))
    if not m:
        raise ValueError(f"unsupported iso date: {iso!r}")
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    month_name = next(k for k, v in _MONTHS.items() if v == month)
    patterns = [
        rf"(?<!\d){re.escape(iso)}(?!\d)",
        rf"\b{month_name}\s+{day}\w*\,?\s+{year}\b",
        rf"\b{month_name[:3]}\.?\s+{day}\w*\,?\s+{year}\b",
        rf"\b{day}\w*\s+{month_name}\,?\s+{year}\b",
    ]
    return any(_affirmative_search(p, normalized) for p in patterns)


def contains_iso_or_slash_date(text, iso):
    """'2026-08-19' or '2026/08/19' (unambiguous machine forms)."""
    normalized = normalize_text(text)
    y, m, d = str(iso).split("-")
    patterns = [rf"(?<!\d){y}-{m}-{d}(?!\d)", rf"(?<!\d){y}/{m}/{d}(?!\d)"]
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
    """Raise ValueError unless both snapshots are genuine Chess.com databases derived from the frozen seed."""
    for db_path in (initial_db, after_db):
        tables = {r["name"] for r in db_query(
            db_path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(TABLES):
            raise ValueError(f"unexpected tables in {db_path}: {sorted(tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    observed_hash = schema_sha256(initial_db)
    if observed_hash != SCHEMA_SHA256:
        raise ValueError(f"unsupported chess_com schema hash: {observed_hash}")
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
        raise ValueError(f"initial database is not the frozen chess_com seed: rows digest {digest}")
    # benchmark users keep their identity columns in the after snapshot
    after_users = {r["email"]: (int(r["id"]), r["username"])
                   for r in db_query(after_db, "SELECT id, username, email FROM users")}
    if any(after_users.get(email) != ident for email, ident in SEED_USERS.items()):
        raise ValueError("benchmark user identities changed in the after snapshot")


def resolve_snapshots(args, task_id):
    """Return validated (initial_db, after_db) or fail closed."""
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) chess_com database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_id_for_email(db_path, email):
    rows = db_query(db_path, "SELECT id FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1", (email,))
    return int(rows[0]["id"]) if rows else None


def user_row(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1", (email,))
    return dict(rows[0]) if rows else None


def leaderboard_row(db_path, category, rank):
    rows = db_query(db_path, "SELECT * FROM leaderboard_entries WHERE category = ? AND rank = ? LIMIT 1",
                    (category, rank))
    return dict(rows[0]) if rows else None


def follows_for(db_path, user_id):
    return {int(r["followed_id"]) for r in db_query(
        db_path, "SELECT followed_id FROM follows WHERE follower_id = ?", (user_id,))}


def club_membership_ids(db_path, user_id):
    return {int(r["club_id"]) for r in db_query(
        db_path, "SELECT club_id FROM club_memberships WHERE user_id = ?", (user_id,))}


def lesson_progress_rows(db_path, user_id):
    return [dict(r) for r in db_query(
        db_path, "SELECT * FROM lesson_progress WHERE user_id = ? ORDER BY id", (user_id,))]


def solved_attempt_count(db_path, user_id):
    return int(db_query(db_path, "SELECT COUNT(*) AS n FROM puzzle_attempts WHERE user_id = ? AND solved = 1",
                        (user_id,))[0]["n"])


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


def check_signed_in_as(judge, traj, email, username):
    judge.check("visited_login_page", navigated_to_path(traj, "/login"), "required_path=/login")
    judge.check("entered_expected_account_identity", entered_identity(traj, email, username),
                f"expected one of {email!r}/{username!r} in an input step; observed_inputs={input_texts(traj)!r}")


def check_visited_path(judge, traj, name, path):
    return judge.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_visited_path_with_params(judge, traj, name, path, params):
    return judge.check(name, navigated_to_path_with_params(traj, path, params),
                       f"required_path={path} with params={params!r}")


def check_search_visited(judge, traj, tokens_any, name="visited_search_results"):
    return judge.check(name, search_visited(traj, tokens_any),
                       f"required=/search?q=<any of {sorted(tokens_any)!r}>; observed_queries={search_queries(traj)!r}")


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
