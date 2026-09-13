#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for 4shared task verification.

Philosophy: DETERMINISTIC FIRST, no LLM in the verdict path.
  1. Run-package identity (anti-tamper): exact task id, agent_done, non-empty
     final answer, every recorded URL on the same loopback origin AND port as
     start_url, every referenced screenshot present and PNG-framed.
  2. Navigation gate (anti knowledge-shortcut): the agent MUST have opened the
     on-site page(s) that carry the answer (exact /file/<slug> paths, /search,
     /category/<c>, /login, /my-files, ...), in the required order where the
     task implies one.
  3. Answer check: token / number / filename containment against ground truth
     that is HARDCODED in each verify_N.py (never in tasks.jsonl).
  4. SQLite after-state (stateful tasks): exact allowed row deltas against the
     initial snapshot; every other table and every unrelated row must be
     byte-for-row identical. Read-only tasks require ALL tables unchanged.
  5. The llm_* helpers are kept for API parity with merriam_webster's lib; no
     verifier in this suite depends on them, and --no_llm short-circuits them.

Input signature (per task):
  --run_dir DIR      agent run: trajectory.json + screenshots/step_NNN.png
                     (+ optional initial.db / after.db snapshots inside DIR)
  --initial_db PATH  initial-state SQLite DB (default: <run_dir>/initial.db, else
                     docker cp instance_seed from --container)
  --after_db PATH    after-state SQLite DB (default: <run_dir>/after.db, else
                     docker cp instance from --container)
  --container NAME   docker container to fetch DBs from ($WH_CONTAINER or wh-review)
  --no_llm True      skip LLM helpers (they are unused anyway)
Output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 PASS / 1 FAIL.

NOTE: no `from __future__ import annotations` here on purpose — simpleArgParser
reads the VerifyArgs dataclass annotations at runtime and postponed annotations
would turn `str` into the string "str" (argparse: "'str' is not callable").
"""
import atexit
import base64
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
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

SITE = "4shared"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

EXPECTED_TABLES = {"comments", "downloads", "favorites", "files", "folders",
                   "plan_orders", "saved_files", "shared_links", "users"}
SEED_COUNTS = {"users": 4, "files": 146, "folders": 16, "favorites": 16, "saved_files": 12,
               "downloads": 8, "shared_links": 4, "comments": 12, "plan_orders": 1}
SEED_PUBLIC_FILES = 122
USER_IDS = {"alice.j@test.com": 1, "bob.c@test.com": 2, "carol.d@test.com": 3, "david.k@test.com": 4}
ALL_TABLES = ("users", "folders", "files", "favorites", "saved_files", "downloads",
              "shared_links", "comments", "plan_orders")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- CLI
import simpleArgParser as sap  # noqa: E402  (available in the agent_demo env)


def parse_args():
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
    return sap.parse_args(VerifyArgs)


# ---------------------------------------------------------------- trajectory
def load_run(run_dir) -> dict:
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(traj, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))} if (d / "screenshots").is_dir() else {}
    return traj


def final_answer(traj) -> str:
    return str(traj.get("final_answer") or "").strip()


def trajectory_urls(traj) -> list[str]:
    urls: list[str] = []
    if traj.get("start_url"):
        urls.append(str(traj["start_url"]))
    for s in traj.get("steps") or []:
        if not isinstance(s, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            if s.get(key):
                urls.append(str(s[key]))
        params = s.get("params") if isinstance(s.get("params"), dict) else {}
        if s.get("action") == "navigate" and params.get("url"):
            urls.append(str(params["url"]))
    if traj.get("final_url"):
        urls.append(str(traj["final_url"]))
    return urls


def step_urls(traj) -> list[str]:
    return [str(s.get("url", "")) for s in traj.get("steps") or [] if isinstance(s, dict)]


def is_site_url(url: str) -> bool:
    """HTTP(S) URL on a loopback host (any port)."""
    p = urlparse(str(url or ""))
    if p.scheme not in {"http", "https"} or not p.hostname:
        return False
    host = p.hostname.casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def same_origin_as_start(url: str, start_url: str) -> bool:
    """Loopback + same scheme/host/port as start_url (walmart-style hardening)."""
    try:
        o, s = urlparse(str(url or "")), urlparse(str(start_url or ""))
    except ValueError:
        return False
    return (is_site_url(url) and is_site_url(start_url) and o.scheme == s.scheme
            and (o.hostname or "").casefold() == (s.hostname or "").casefold()
            and o.port == s.port and not o.username and not o.password)


def site_urls(traj) -> list[str]:
    return [u for u in trajectory_urls(traj) if is_site_url(u)]


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def navigated_to_path(traj, path: str) -> bool:
    """Exact mirror path (query ignored) somewhere in the recorded history."""
    want = normalized_url_path(path)
    return any(normalized_url_path(u) == want for u in site_urls(traj))


def navigated_to(traj, substr: str, times: int = 1) -> bool:
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs: Iterable[str]) -> bool:
    return any(navigated_to(traj, s) for s in substrs)


def detail_visited(traj, slug: str) -> bool:
    return navigated_to_path(traj, f"/file/{slug}")


def query_params(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(url or "")).query, keep_blank_values=True)


def search_visited(traj, any_tokens: Iterable[str] = (), all_tokens: Iterable[str] = (),
                   category: str | None = None) -> bool:
    """Some /search visit whose q contains every `all_tokens` and any of `any_tokens`
    (normalized substrings) and, if given, whose category param equals `category`."""
    any_t = [normalize_text(t) for t in any_tokens]
    all_t = [normalize_text(t) for t in all_tokens]
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        q = query_params(u)
        qtext = normalize_text(" ".join(q.get("q") or []))
        if all_t and not all(t in qtext for t in all_t):
            continue
        if any_t and not any(t in qtext for t in any_t):
            continue
        if category is not None and normalize_text(category) not in [normalize_text(c) for c in q.get("category") or []]:
            continue
        return True
    return False


def category_visited(traj, category: str) -> bool:
    """/category/<c> OR a /search visit filtered to that category."""
    return navigated_to_path(traj, f"/category/{category.lower()}") or search_visited(traj, category=category)


def paths_in_order(traj, paths: Sequence[str]) -> bool:
    """Each path (exact, query ignored) appears after the previous one in history."""
    urls = site_urls(traj)
    cursor = 0
    for want in paths:
        want = normalized_url_path(want)
        for i in range(cursor, len(urls)):
            if normalized_url_path(urls[i]) == want:
                cursor = i + 1
                break
        else:
            return False
    return True


def first_index_of_path(traj, path: str) -> int | None:
    want = normalized_url_path(path)
    for i, u in enumerate(site_urls(traj)):
        if normalized_url_path(u) == want:
            return i
    return None


def typed_texts(traj) -> list[str]:
    out = []
    for s in traj.get("steps") or []:
        if isinstance(s, dict) and s.get("action") == "input":
            params = s.get("params") if isinstance(s.get("params"), dict) else {}
            if params.get("text") is not None:
                out.append(str(params["text"]))
    return out


def typed_email(traj, email: str) -> bool:
    want = normalize_text(email)
    return any(normalize_text(t) == want for t in typed_texts(traj))


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(str(name)).name)
    return p if (p and p.exists()) else None


def last_shot(traj):
    for s in reversed(traj.get("steps") or []):
        p = _shot(traj, s.get("screenshot_after")) or _shot(traj, s.get("screenshot_before"))
        if p:
            return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


def screenshots_ok(traj) -> tuple[bool, str]:
    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "no steps"
    checked = 0
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            return False, f"step {i} is not an object"
        for key in ("screenshot_before", "screenshot_after"):
            name = s.get(key)
            rel = Path(str(name or ""))
            if not name or rel.is_absolute() or ".." in rel.parts:
                return False, f"step {i} has unsafe {key}={name!r}"
            p = _shot(traj, name)
            if p is None:
                return False, f"step {i} is missing {key}={name!r}"
            try:
                head = p.read_bytes()[:8]
            except OSError as exc:
                return False, f"step {i} {key} unreadable: {exc}"
            if head != PNG_MAGIC or p.stat().st_size <= 8:
                return False, f"step {i} {key} is not a PNG"
            checked += 1
    return True, f"{checked} PNG screenshots present"


# ---------------------------------------------------------------- text matching
def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("×", "x").replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def norm(s):  # merriam-compatible alias
    return normalize_text(s)


def _negated(text: str, m: re.Match) -> bool:
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead|whereas|while)\b", text[:m.start()], flags=re.I)[-1]
    after = text[m.end():m.end() + 40]
    return bool(re.search(r"\b(?:not|no|never|without|wrong|incorrect|isn't|wasn't|isnt|wasnt|neither|nor)\b", before, re.I)
                or re.match(r"\s*(?:is|was|are|were|has|have)?\s*(?:not|wrong|incorrect)\b", after, re.I))


def affirmative_search(pattern: str, text: str, flags: int = 0) -> bool:
    return any(not _negated(text, m) for m in re.finditer(pattern, text, flags))


def contains_all(text: Any, tokens: Iterable[Any]) -> bool:
    t = normalize_text(text)
    return all(bool(tok) and affirmative_search(re.escape(tok), t) for tok in (normalize_text(x) for x in tokens))


def contains_any(text: Any, tokens: Iterable[Any]) -> bool:
    t = normalize_text(text)
    return any(bool(tok) and affirmative_search(re.escape(tok), t) for tok in (normalize_text(x) for x in tokens))


def answer_equals(final, expected) -> bool:
    return normalize_text(final) == normalize_text(expected)


def contains_filename(text: Any, filename: str) -> bool:
    """The exact filename (stem + extension) appears; whitespace/case/quote tolerant."""
    t = normalize_text(text)
    want = normalize_text(filename)
    return affirmative_search(r"(?<![a-z0-9])" + re.escape(want) + r"(?![a-z0-9])", t)


def contains_number(text: Any, number: int | str) -> bool:
    """`number` as a standalone integer (not inside a longer digit run, a decimal, a
    time like 10:45, a ratio like 1/80, or a version like 5.0.0); word form for <= 20."""
    t = normalize_text(text)
    n = str(int(number))
    pattern = rf"(?<![\d.,:/])(?<!\d\.){n}(?![\d]|[.,]\d|:\d|/\d|\s*(?:st|nd|rd|th)\b)"
    if affirmative_search(pattern, t):
        return True
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
             11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
             18: "eighteen", 19: "nineteen", 20: "twenty"}
    w = words.get(int(number))
    return bool(w and affirmative_search(rf"\b{w}\b", t))


def contains_runtime(text: Any, mmss: str) -> bool:
    """`27:03` also accepted as `27 min 3 s`, `27 minutes 03 seconds`, `27m03s`."""
    m, s = mmss.split(":")
    t = normalize_text(text)
    pats = [rf"(?<!\d){int(m)}:{int(s):02d}(?!\d)",
            rf"(?<!\d){int(m)}\s*(?:min(?:ute)?s?|m)\b\.?\s*(?:and\s*)?{int(s)}\s*(?:sec(?:ond)?s?|s)\b"]
    return any(affirmative_search(p, t) for p in pats)


def contains_size(text: Any, human: str) -> bool:
    """`4.2 MB` tolerant of `4.2MB`, `4.2 mb`, `4.2 megabytes`."""
    num, unit = human.split()
    t = normalize_text(text)
    unit_pat = {"kb": r"(?:kb|kib|kilobytes?)", "mb": r"(?:mb|mib|megabytes?)", "gb": r"(?:gb|gib|gigabytes?)", "b": r"(?:b|bytes?)"}[unit.lower()]
    return affirmative_search(rf"(?<![\d.]){re.escape(num)}\s*{unit_pat}\b", t)


def contains_resolution(text: Any, w: int, h: int) -> bool:
    t = normalize_text(text)
    return affirmative_search(rf"(?<!\d){w}\s*(?:x|by|\*)\s*{h}(?!\d)", t)


def first_mentioned(text: Any, keys: Sequence[str]) -> str | None:
    t = normalize_text(text)
    best = None
    for k in keys:
        i = t.find(normalize_text(k))
        if i >= 0 and (best is None or i < best[0]):
            best = (i, k)
    return best[1] if best else None


def claims_winner(text: Any, winner_key: str, loser_keys: Sequence[str],
                  cue: str = r"longer|longest|most|more|highest|largest|biggest",
                  inverse_cue: str = r"shorter|shortest|less|fewer|fewest|smaller|smallest|lower|lowest") -> bool:
    """Deterministic reading of a comparison claim.

    The answer must name `winner_key`. In every sentence that carries a comparison
    cue, the item the sentence credits is resolved as: the item nearest BEFORE the
    cue (the grammatical subject: "X is longer than Y"); if none precedes it, the
    item nearest AFTER it ("the longer one is X"); "former"/"latter" near the cue
    select the first/last item named in that sentence. A positive cue must credit
    the winner and an inverse cue must not. With no cue sentence at all, the winner
    must simply be the first item mentioned.
    """
    t = normalize_text(text)
    w = normalize_text(winner_key)
    keys = [w] + [normalize_text(k) for k in loser_keys]
    if w not in t:
        return False
    saw_cue = False
    # Split only on sentence punctuation followed by whitespace/end so that the
    # "." inside filenames ("…Seas.epub", "…Summer.mp3") never cuts a sentence.
    for sentence in re.split(r"[.!?;\n]+(?=\s|$)", t):
        positions = sorted((sentence.find(k), k) for k in keys if k in sentence)
        if not positions:
            continue
        for m in re.finditer(rf"\b(?:{cue}|{inverse_cue})\b", sentence):
            saw_cue = True
            window = sentence[max(0, m.start() - 40):m.end() + 40]
            if re.search(r"\blatter\b", window):
                credited = positions[-1][1]
            elif re.search(r"\bformer\b", window):
                credited = positions[0][1]
            else:
                before = [k for p, k in positions if p < m.start()]
                after = [k for p, k in positions if p > m.start()]
                credited = before[-1] if before else (after[0] if after else None)
            inverse = re.fullmatch(rf"(?:{inverse_cue})", m.group())
            if credited is not None and ((credited != w) if not inverse else (credited == w)):
                return False
    if not saw_cue:
        return first_mentioned(t, keys) == w
    return True


# ---------------------------------------------------------------- SQLite
def db_query(db_path, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    fd, dest = tempfile.mkstemp(prefix=f"{SITE}_{kind}_", suffix=".db")
    os.close(fd)
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    r = subprocess.run(["docker", "cp", src, dest], capture_output=True, text=True)
    if r.returncode:
        Path(dest).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip() or r.stdout.strip()}")
    atexit.register(Path(dest).unlink, missing_ok=True)
    return dest


def resolve_db(explicit: str | None, container: str, kind: str) -> str | None:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def table_rows(db_path, table: str) -> list[tuple]:
    if table not in EXPECTED_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return [tuple(r) for r in db_query(db_path, f"SELECT * FROM {table} ORDER BY id")]


def table_columns(db_path, table: str) -> list[str]:
    if table not in EXPECTED_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return [r["name"] for r in db_query(db_path, f"PRAGMA table_info({table})")]


def row_by_id(db_path, table: str, row_id: int) -> dict | None:
    if table not in EXPECTED_TABLES:
        raise ValueError(f"unsupported table: {table}")
    rows = db_query(db_path, f"SELECT * FROM {table} WHERE id = ?", (int(row_id),))
    return dict(rows[0]) if rows else None


def rows_where(db_path, table: str, where: str, params: Sequence[Any] = ()) -> list[dict]:
    if table not in EXPECTED_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return [dict(r) for r in db_query(db_path, f"SELECT * FROM {table} WHERE {where} ORDER BY id", params)]


def table_delta(initial_db, after_db, table: str) -> dict[str, list]:
    before = {int(r[0]): r for r in table_rows(initial_db, table)}
    after = {int(r[0]): r for r in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {"added": [after[k] for k in sorted(after.keys() - before.keys())],
            "removed": [before[k] for k in sorted(before.keys() - after.keys())],
            "changed": [(before[k], after[k]) for k in sorted(common) if before[k] != after[k]]}


def added_rows(initial_db, after_db, table: str) -> list[dict]:
    cols = table_columns(after_db, table)
    return [dict(zip(cols, r)) for r in table_delta(initial_db, after_db, table)["added"]]


def tables_unchanged(initial_db, after_db, tables: Iterable[str]) -> dict[str, bool]:
    return {t: table_rows(initial_db, t) == table_rows(after_db, t) for t in tables}


def rows_unchanged_except(initial_db, after_db, table: str, excluded_ids: Iterable[int]) -> bool:
    ex = {int(i) for i in excluded_ids}
    before = [r for r in table_rows(initial_db, table) if int(r[0]) not in ex]
    after = [r for r in table_rows(after_db, table) if int(r[0]) not in ex]
    return before == after


def row_changed_only_in(initial_db, after_db, table: str, row_id: int, allowed_cols: Iterable[str]) -> tuple[bool, dict]:
    """Row `row_id` differs from initial ONLY in `allowed_cols`; returns (ok, diff)."""
    b, a = row_by_id(initial_db, table, row_id), row_by_id(after_db, table, row_id)
    if b is None or a is None:
        return False, {"missing": True}
    diff = {k: (b[k], a[k]) for k in b if b[k] != a.get(k)}
    return set(diff) <= set(allowed_cols), diff


def _schema_objects(db_path) -> list[tuple]:
    return [tuple(r) for r in db_query(
        db_path, "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]


def validate_snapshot_contract(initial_db, after_db) -> None:
    for label, db in (("initial", initial_db), ("after", after_db)):
        tables = {r["name"] for r in db_query(db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != EXPECTED_TABLES:
            raise ValueError(f"{label} DB has unexpected tables: {sorted(tables)}")
    if _schema_objects(initial_db) != _schema_objects(after_db):
        raise ValueError("initial and after database schemas differ")
    counts = {t: len(table_rows(initial_db, t)) for t in SEED_COUNTS}
    if counts != SEED_COUNTS:
        raise ValueError(f"initial DB row counts differ from the 4shared seed: expected={SEED_COUNTS} observed={counts}")
    public = db_query(initial_db, "SELECT COUNT(*) AS n FROM files WHERE public = 1 AND deleted = 0")[0]["n"]
    if public != SEED_PUBLIC_FILES:
        raise ValueError(f"initial DB public file count {public} != {SEED_PUBLIC_FILES}")
    for email, uid in USER_IDS.items():
        rows = db_query(initial_db, "SELECT id FROM users WHERE email = ?", (email,))
        if not rows or int(rows[0]["id"]) != uid:
            raise ValueError(f"initial DB lacks benchmark user {email} with id {uid}")


def resolve_snapshots(args, task_id: str) -> tuple[str, str]:
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable", "both initial and after 4shared database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_id_for_email(db_path, email: str) -> int | None:
    rows = db_query(db_path, "SELECT id FROM users WHERE lower(email) = lower(?)", (email,))
    return int(rows[0]["id"]) if rows else None


def favorite_file_ids(db_path, user_id: int) -> set[int]:
    return {int(r["file_id"]) for r in db_query(db_path, "SELECT file_id FROM favorites WHERE user_id = ?", (user_id,))}


def saved_file_ids(db_path, user_id: int) -> set[int]:
    return {int(r["file_id"]) for r in db_query(db_path, "SELECT file_id FROM saved_files WHERE user_id = ?", (user_id,))}


def public_catalog_unchanged_except(initial_db, after_db, file_ids: Iterable[int] = ()) -> bool:
    """Every seeded public catalog row is identical except the listed ids."""
    ex = {int(i) for i in file_ids}
    b = [r for r in rows_where(initial_db, "files", "public = 1") if r["id"] not in ex]
    a_map = {r["id"]: r for r in rows_where(after_db, "files", "public = 1")}
    return all(a_map.get(r["id"]) == r for r in b)


# ---------------------------------------------------------------- LLM utilities (parity only; unused by the verdicts)
_NO_LLM = False


def _llm_config():
    return os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_BASE_URL", ""), os.environ.get("JUDGE_MODEL", "")


def _chat(messages, max_tokens=1024):
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    return _verdict(_chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\nGround-truth answer (ANCHOR): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\nLine 1: PASS or FAIL. Line 2: one-sentence reason."}]))


def llm_screenshot_shows(shot_path, must_show, question=""):
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    return _verdict(_chat([{"role": "user", "content": [
        {"type": "text", "text": f"Only visibly rendered pixels count. Question: {question}\nExpected content: {must_show}\nLine 1: PASS or FAIL. Line 2: evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]))


# ---------------------------------------------------------------- judge harness
class Judge:
    def __init__(self, task_id: str, no_llm: bool = False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, cond: Any, evidence: str = "", llm: bool = False) -> bool:
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no_llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason or "all checks passed", "evidence": self.evidence},
                         ensure_ascii=False, indent=2))
        sys.exit(0 if self.ok else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({"task_id": task_id, "pass": False, "infra_error": True, "reason": reason,
                      "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)


# ---------------------------------------------------------------- composite checks
def check_trajectory_identity(j: Judge, traj: dict, task_id: str) -> None:
    fa = final_answer(traj)
    j.check("final_answer_nonempty", bool(fa), f"final_answer={fa[:160]!r}")
    j.check("trajectory_task_matches", str(traj.get("task_id") or "").strip() == task_id,
            f"expected={task_id!r} observed={traj.get('task_id')!r}")
    j.check("trajectory_completed", traj.get("terminated") is True and traj.get("termination_reason") == "agent_done",
            f"terminated={traj.get('terminated')!r} reason={traj.get('termination_reason')!r}")
    steps = traj.get("steps")
    j.check("trajectory_has_steps", isinstance(steps, list) and bool(steps), f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    urls = trajectory_urls(traj)
    bad = [u for u in urls if not same_origin_as_start(u, traj.get("start_url", ""))]
    j.check("all_urls_on_start_origin", bool(urls) and not bad,
            f"start_url={traj.get('start_url')!r} n_urls={len(urls)} off_origin={bad[:3]!r}")
    ok, ev = screenshots_ok(traj)
    j.check("screenshots_present_png", ok, ev)


def check_signed_in_as(j: Judge, traj: dict, email: str) -> None:
    j.check("visited_login_page", navigated_to_path(traj, "/login"), "required_path=/login")
    j.check("typed_account_email", typed_email(traj, email), f"expected_email={email!r} typed={typed_texts(traj)[:6]!r}")


def check_visited_path(j: Judge, traj: dict, name: str, path: str) -> bool:
    return j.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_detail_visited(j: Judge, traj: dict, slug: str) -> bool:
    return j.check(f"visited_detail_{slug}", detail_visited(traj, slug), f"required_path=/file/{slug}")


def check_search_or_category(j: Judge, traj: dict, name: str, any_tokens: Iterable[str] = (), categories: Iterable[str] = ()) -> bool:
    ok = search_visited(traj, any_tokens=any_tokens) or any(navigated_to_path(traj, f"/category/{c.lower()}") for c in categories)
    return j.check(name, ok, f"required=/search?q~{list(any_tokens)!r} or /category/{list(categories)!r}; observed={[u for u in site_urls(traj) if '/search' in u or '/category/' in u][:6]!r}")


def check_paths_in_order(j: Judge, traj: dict, name: str, paths: Sequence[str]) -> bool:
    return j.check(name, paths_in_order(traj, paths), f"required_order={list(paths)!r}; observed={[normalized_url_path(u) for u in site_urls(traj)]!r}")


def check_tables_unchanged(j: Judge, initial_db, after_db, tables: Iterable[str], prefix: str = "") -> None:
    for t, same in tables_unchanged(initial_db, after_db, tables).items():
        j.check(f"{prefix}{t}_unchanged", same,
                f"table={t} initial_rows={len(table_rows(initial_db, t))} after_rows={len(table_rows(after_db, t))}")


def check_read_only(j: Judge, initial_db, after_db) -> None:
    """Read-only tasks: every table row-identical (the seed is the whole world)."""
    check_tables_unchanged(j, initial_db, after_db, ALL_TABLES, prefix="read_only_")


def check_download_recorded(j: Judge, initial_db, after_db, file_id: int, user_id: int | None = None, allow_anonymous: bool = True) -> None:
    """Exactly one new downloads row for file_id (+1 download_count on that file)."""
    added = added_rows(initial_db, after_db, "downloads")
    mine = [r for r in added if int(r["file_id"]) == int(file_id)]
    # user_id=None means "any account (or anonymous when allowed)"; a concrete
    # user_id must match exactly (anonymous only if allow_anonymous).
    who_ok = all((user_id is None and (allow_anonymous or r["user_id"] is not None))
                 or (user_id is not None and (r["user_id"] == user_id or (allow_anonymous and r["user_id"] is None)))
                 for r in mine)
    j.check("download_row_added", len(added) == 1 and len(mine) == 1 and who_ok,
            f"added_downloads={[(r['file_id'], r['user_id']) for r in added]!r} expected_file={file_id} expected_user={user_id}")
    b, a = row_by_id(initial_db, "files", file_id), row_by_id(after_db, "files", file_id)
    ok, diff = row_changed_only_in(initial_db, after_db, "files", file_id, ("download_count",))
    j.check("download_count_incremented", ok and b and a and int(a["download_count"]) == int(b["download_count"]) + 1,
            f"file={file_id} before={b and b['download_count']} after={a and a['download_count']} diff={diff!r}")
