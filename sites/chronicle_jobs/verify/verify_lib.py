#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for chronicle_jobs task verification.

Philosophy: DETERMINISTIC FIRST, no LLM in the verdict path.
  1. Run-package identity (anti-tamper): exact task id, agent_done, non-empty
     final answer, every recorded URL on the same loopback origin AND port as
     start_url, every referenced screenshot present and PNG-framed.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have performed
     the on-site interaction the task names — keyword search (/searchjobs/ or
     /jobs/ with Keywords=), location search (radialtown=), facet/category
     browse (/jobs/<slug>/...), job detail (/job/<id>/<slug>/), employer hub
     (/employer/<ref>/<slug>/), career article (/career-resources/<slug>/),
     account pages (/logon, /your-jobs/, /newalert, /profile/, /profilecv/) —
     in the order the task implies where one is implied.
  3. Answer check: token / number / date / salary containment against ground
     truth that is HARDCODED in each verify_N.py (never in tasks.jsonl).
  4. SQLite after-state (stateful tasks): exact allowed row deltas against the
     instance_seed snapshot; read-only tasks require all tables unchanged.
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

SITE = "chronicle_jobs"
DB_FILENAME = "chronicle_jobs.db"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")

EXPECTED_TABLES = {"applications", "articles", "categories", "contact_messages",
                   "employers", "facet_values", "job_alerts", "job_categories",
                   "job_facets", "jobs", "landing_pages", "saved_jobs", "users"}
SEED_COUNTS = {"applications": 6, "articles": 14, "categories": 276,
               "contact_messages": 0, "employers": 452, "facet_values": 90,
               "job_alerts": 7, "job_categories": 6323, "job_facets": 5762,
               "jobs": 1522, "landing_pages": 20, "saved_jobs": 14, "users": 4}
ALL_TABLES = ("applications", "articles", "categories", "contact_messages",
              "employers", "facet_values", "job_alerts", "job_categories",
              "job_facets", "jobs", "landing_pages", "saved_jobs", "users")
USER_IDS = {"alice.j@test.com": 1, "bob.c@test.com": 2, "carol.d@test.com": 3, "david.k@test.com": 4}
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
    args = sap.parse_args(VerifyArgs)
    if bool(args.initial_db) != bool(args.after_db):
        raise SystemExit("initial.db and after.db must be supplied together")
    return args


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
    """Loopback + same scheme/host/port as start_url."""
    try:
        o, s = urlparse(str(url or "")), urlparse(str(start_url or ""))
    except ValueError:
        return False
    return (is_site_url(url) and is_site_url(start_url) and o.scheme == s.scheme
            and (o.hostname or "").casefold() == (s.hostname or "").casefold()
            and o.port == s.port and not o.username and not o.password)


def site_urls(traj) -> list[str]:
    # Navigation claims in action parameters are not evidence of arrival.
    return [str(step.get(field)) for step in traj.get('steps', [])
            for field, frame in [('url', 'screenshot_before'), ('url_before', 'screenshot_before'), ('url_after', 'screenshot_after')]
            if step.get(field) and step.get(frame) and is_site_url(step[field])]


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def navigated_to_path(traj, path: str) -> bool:
    """Exact mirror path (query ignored) somewhere in the recorded history."""
    want = normalized_url_path(path)
    return any(normalized_url_path(u) == want for u in site_urls(traj))


def navigated_to_path_prefix(traj, prefix: str) -> bool:
    """A site URL whose path equals <prefix> or starts with <prefix>/ — accepts
    browse paths with page segments (/jobs/adjunct/2/)."""
    want = normalized_url_path(prefix)
    return any(p == want or p.startswith(want + "/") for p in (normalized_url_path(u) for u in site_urls(traj)))


def navigated_to(traj, substr: str, times: int = 1) -> bool:
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def query_params(url: str) -> dict[str, list[str]]:
    values = parse_qs(urlparse(str(url or "")).query, keep_blank_values=True)
    return values if all(len(v) == 1 for v in values.values()) else {}


def detail_visited(traj, job_id: int, slug: str) -> bool:
    return navigated_to_path(traj, f"/job/{job_id}/{slug}")


def browse_visited(traj, slug: str) -> bool:
    """/jobs/<slug>[/page] browse (facet or category), query ignored."""
    return navigated_to_path_prefix(traj, f"/jobs/{slug}")


def _norm_tokens(value: str) -> list[str]:
    return [normalize_text(t) for t in re.split(r"\W+", str(value or "").lower()) if t]


def search_visited(traj, any_tokens: Iterable[str] = (), all_tokens: Iterable[str] = (),
                   location_any: Iterable[str] = ()) -> bool:
    """A /searchjobs/ or /jobs/ visit whose Keywords param contains every
    `all_tokens` and any of `any_tokens` (word-token containment), and whose
    radialtown (location) param contains any of `location_any`."""
    any_t = [normalize_text(t) for t in any_tokens]
    all_t = [normalize_text(t) for t in all_tokens]
    loc_t = [normalize_text(t) for t in location_any]
    for u in site_urls(traj):
        p = normalized_url_path(u)
        if p not in ("/searchjobs", "/jobs"):
            continue
        q = query_params(u)
        kw = " ".join(q.get("Keywords") or q.get("keywords") or [])
        kwtoks = set(_norm_tokens(kw))
        if all_t and not all(t in kwtoks for t in all_t):
            continue
        if any_t and not any(t in kwtoks for t in any_t):
            continue
        if loc_t:
            loc = normalize_text(" ".join(q.get("radialtown") or q.get("location") or []))
            if not any(t in loc for t in loc_t):
                continue
        return True
    return False


def location_search_visited(traj, location_any: Iterable[str]) -> bool:
    """A search with an empty Keywords box and a radialtown location value
    (the task-4 style location-only search)."""
    loc_t = [normalize_text(t) for t in location_any]
    for u in site_urls(traj):
        p = normalized_url_path(u)
        if p not in ("/searchjobs", "/jobs"):
            continue
        q = query_params(u)
        kw = " ".join(q.get("Keywords") or q.get("keywords") or []).strip()
        if kw:
            continue
        loc = normalize_text(" ".join(q.get("radialtown") or q.get("location") or []))
        if any(t in loc for t in loc_t):
            return True
    return False


def paths_in_order(traj, paths: Sequence[str]) -> bool:
    """Each path (exact, query ignored) appears after the previous one."""
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


def screenshots_ok(traj) -> tuple[bool, str]:
    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "no steps"
    checked = 0
    hashes = set()
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
            try:
                from PIL import Image
                with Image.open(p) as image:
                    if image.format != "PNG" or image.width < 200 or image.height < 120:
                        return False, "invalid screenshot dimensions or format"
                    image.verify()
                with Image.open(p) as image:
                    image.load()
            except (OSError, ValueError, SyntaxError):
                return False, f"step {i} has an undecodable screenshot"
            import hashlib
            hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
            checked += 1
    if len(hashes) < min(3, len(steps)):
        return False, "insufficient distinct rendered frames"
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


def contains_number(text: Any, number: int | str) -> bool:
    """`number` as a standalone integer (not inside a longer digit run, a
    decimal, a time, a ratio, a version, or a dollar range like 66,462-74,800);
    word form for <= 20."""
    t = normalize_text(text)
    n = str(int(number))
    pattern = rf"(?<![\d.,:/$])(?<!\d\.){n}(?![\d]|[.,]\d|:\d|/\d|\s*(?:st|nd|rd|th)\b)"
    if affirmative_search(pattern, t):
        return True
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
             11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
             18: "eighteen", 19: "nineteen", 20: "twenty"}
    w = words.get(int(number))
    return bool(w and affirmative_search(rf"\b{w}\b", t))


def contains_dollar_amount(text: Any, amount: str) -> bool:
    """A dollar amount like '$80,000', '$12,000', '$300,000' — tolerant of a
    missing comma ('$80000'), of '$80,000.00', and of spacing after the $."""
    t = normalize_text(text)
    digits = re.sub(r"[^\d]", "", str(amount))
    n_comma = f"{int(digits):,}"
    n_plain = str(int(digits))
    pat_comma = rf"\$\s?{re.escape(n_comma)}(?![\d])"
    pat_plain_dollar = rf"\$\s?{re.escape(n_plain)}(?![\d])"
    pat_bare_comma = rf"(?<![\d.]){re.escape(n_comma)}(?![\d])"
    return bool(affirmative_search(pat_comma, t) or affirmative_search(pat_plain_dollar, t)
                or affirmative_search(pat_bare_comma, t))


def contains_month_date(text: Any, date_label: str) -> bool:
    """A date label like 'Sep 21, 2026' / 'October 5, 2026' — tolerant of
    'September 21, 2026' vs 'Sep 21 2026' style variance."""
    t = normalize_text(text)
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", date_label.strip())
    if not m:
        return contains_all(text, [date_label])
    month, day, year = m.group(1), m.group(2), m.group(3)
    month3 = month[:3].lower()  # normalize_text casefolds the haystack
    pat = rf"\b{month3}[a-z]*\.?\s+{int(day)}(?:st|nd|rd|th)?,?\s+{year}\b"
    return affirmative_search(pat, t)


def contains_url_path(text: Any, fragment: str) -> bool:
    return normalize_text(fragment) in normalize_text(text)


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
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{DB_FILENAME}"
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
    cols = table_columns(db_path, table)
    if "id" in cols:
        return [tuple(r) for r in db_query(db_path, f"SELECT * FROM {table} ORDER BY id")]
    # association tables (job_categories / job_facets) have a composite PK and
    # no id column — order by every column for a deterministic row sequence.
    order = ", ".join(f'"{c}"' for c in cols)
    return [tuple(r) for r in db_query(db_path, f"SELECT * FROM {table} ORDER BY {order}")]


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


def _row_key(row: tuple):
    """Stable key for a row: the id column when present, else the full tuple."""
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return row


def table_delta(initial_db, after_db, table: str) -> dict[str, list]:
    if "id" in table_columns(after_db, table):
        before = {_row_key(r): r for r in table_rows(initial_db, table)}
        after = {_row_key(r): r for r in table_rows(after_db, table)}
    else:
        before = {r: r for r in table_rows(initial_db, table)}
        after = {r: r for r in table_rows(after_db, table)}
    common = before.keys() & after.keys()
    return {"added": [after[k] for k in sorted(after.keys() - before.keys(), key=repr)],
            "removed": [before[k] for k in sorted(before.keys() - after.keys(), key=repr)],
            "changed": [(before[k], after[k]) for k in sorted(common, key=repr) if before[k] != after[k]]}


def added_rows(initial_db, after_db, table: str) -> list[dict]:
    cols = table_columns(after_db, table)
    return [dict(zip(cols, r)) for r in table_delta(initial_db, after_db, table)["added"]]


def tables_unchanged(initial_db, after_db, tables: Iterable[str]) -> dict[str, bool]:
    return {t: table_rows(initial_db, t) == table_rows(after_db, t) for t in tables}


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
        raise ValueError(f"initial DB row counts differ from the chronicle_jobs seed: expected={SEED_COUNTS} observed={counts}")
    for email, uid in USER_IDS.items():
        rows = db_query(initial_db, "SELECT id FROM users WHERE email = ?", (email,))
        if not rows or int(rows[0]["id"]) != uid:
            raise ValueError(f"initial DB lacks benchmark user {email} with id {uid}")


def resolve_snapshots(args, task_id: str) -> tuple[str, str]:
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial and after chronicle_jobs database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


def user_id_for_email(db_path, email: str) -> int | None:
    rows = db_query(db_path, "SELECT id FROM users WHERE lower(email) = lower(?)", (email,))
    return int(rows[0]["id"]) if rows else None


def saved_job_rowids(db_path, user_id: int) -> set[int]:
    return {int(r["job_id"]) for r in db_query(db_path, "SELECT job_id FROM saved_jobs WHERE user_id = ?", (user_id,))}


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
    j.check("final_done_step", bool(steps) and steps[-1].get("action") == "done", "completed run ends with done")
    j.check("trajectory_has_steps", isinstance(steps, list) and bool(steps), f"steps={len(steps) if isinstance(steps, list) else 'invalid'}")
    urls = trajectory_urls(traj)
    bad = [u for u in urls if not same_origin_as_start(u, traj.get("start_url", ""))]
    j.check("all_urls_on_start_origin", bool(urls) and not bad,
            f"start_url={traj.get('start_url')!r} n_urls={len(urls)} off_origin={bad[:3]!r}")
    ok, ev = screenshots_ok(traj)
    j.check("screenshots_present_png", ok, ev)


def check_signed_in_as(j: Judge, traj: dict, email: str) -> None:
    j.check("visited_login_page", navigated_to_path(traj, "/logon"), "required_path=/logon")
    j.check("typed_account_email", typed_email(traj, email), f"expected_email={email!r} typed={typed_texts(traj)[:6]!r}")


def check_visited_path(j: Judge, traj: dict, name: str, path: str) -> bool:
    return j.check(name, navigated_to_path(traj, path), f"required_path={path}")


def check_browse(j: Judge, traj: dict, name: str, slug: str) -> bool:
    return j.check(name, browse_visited(traj, slug), f"required_browse=/jobs/{slug}[/...]")


def check_search(j: Judge, traj: dict, name: str, all_tokens: Iterable[str] = (), any_tokens: Iterable[str] = ()) -> bool:
    ok = search_visited(traj, all_tokens=all_tokens, any_tokens=any_tokens)
    return j.check(name, ok, f"required=/searchjobs/ or /jobs/?Keywords=~{list(all_tokens)!r}{list(any_tokens)!r}; "
                             f"observed={[u for u in site_urls(traj) if 'Keywords' in u or 'searchjobs' in u][:6]!r}")


def check_location_search(j: Judge, traj: dict, name: str, location_any: Iterable[str]) -> bool:
    ok = location_search_visited(traj, location_any)
    return j.check(name, ok, f"required=empty-keyword search with radialtown~{list(location_any)!r}; "
                             f"observed={[u for u in site_urls(traj) if 'radialtown' in u][:6]!r}")


def check_detail_visited(j: Judge, traj: dict, job_id: int, slug: str) -> bool:
    return j.check(f"visited_detail_{slug[:40]}", detail_visited(traj, job_id, slug),
                   f"required_path=/job/{job_id}/{slug}/")


def check_account_section(j: Judge, traj: dict, section: str) -> bool:
    ok = any("ActiveSection" in u and section in parse_qs(urlparse(u).query).get("ActiveSection", [])
             and normalized_url_path(u) == "/your-jobs" for u in site_urls(traj)) or navigated_to_path(traj, "/your-jobs")
    return j.check(f"visited_account_{section}", ok, f"required=/your-jobs/?ActiveSection={section} (or /your-jobs/)")


def check_employer_hub(j: Judge, traj: dict, slug: str) -> bool:
    ok = any(normalized_url_path(u).startswith(f"/employer/") and slug in u for u in site_urls(traj))
    return j.check("visited_employer_hub", ok, f"required=/employer/<ref>/{slug}/; "
                                              f"observed={[u for u in site_urls(traj) if '/employer/' in u][:4]!r}")


def check_career_article(j: Judge, traj: dict, slug: str) -> bool:
    return j.check("visited_career_article", navigated_to_path(traj, f"/career-resources/{slug}"),
                   f"required_path=/career-resources/{slug}/")


def check_tables_unchanged(j: Judge, initial_db, after_db, tables: Iterable[str], prefix: str = "") -> None:
    for t, same in tables_unchanged(initial_db, after_db, tables).items():
        j.check(f"{prefix}{t}_unchanged", same,
                f"table={t} initial_rows={len(table_rows(initial_db, t))} after_rows={len(table_rows(after_db, t))}")


def check_read_only(j: Judge, initial_db, after_db) -> None:
    """Read-only tasks: every table row-identical (the seed is the whole world)."""
    check_tables_unchanged(j, initial_db, after_db, ALL_TABLES, prefix="read_only_")


def check_only_rows_added(j: Judge, initial_db, after_db, table: str, expect_n: int,
                          predicate=None, label: str = "") -> list[dict]:
    """Exactly `expect_n` rows added to `table`, nothing removed or changed;
    every added row must satisfy `predicate` (if given)."""
    delta = table_delta(initial_db, after_db, table)
    added = added_rows(initial_db, after_db, table)
    j.check(f"{label or table}_only_additions",
            not delta["removed"] and not delta["changed"] and len(added) == expect_n,
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])} expected_added={expect_n}")
    if predicate is not None:
        for r in added:
            j.check(f"{label or table}_added_row_valid", predicate(r),
                    f"added_row={ {k: r[k] for k in list(r)[:8]} }")
    return added


def check_only_rows_removed(j: Judge, initial_db, after_db, table: str, expect_ids: Iterable[int],
                            label: str = "") -> None:
    """Exactly the rows with ids in `expect_ids` removed from `table`; nothing else."""
    delta = table_delta(initial_db, after_db, table)
    removed_ids = sorted(int(r[0]) for r in delta["removed"])
    j.check(f"{label or table}_only_removals",
            not delta["added"] and not delta["changed"] and removed_ids == sorted(int(i) for i in expect_ids),
            f"removed={removed_ids} expected={sorted(int(i) for i in expect_ids)} added={len(delta['added'])} changed={len(delta['changed'])}")


def row_edited_only_in_with_crlf(initial_db, after_db, table: str, row_id: int,
                                  allowed_cols: Iterable[str]) -> tuple[bool, dict]:
    """Row `row_id` differs ONLY in `allowed_cols`, except that any TEXT column
    may additionally differ by bare LF-vs-CRLF normalization (browsers submit
    textarea values with CRLF; the mirror's /profilecv/ stores them as-is, so an
    honest resume edit also normalizes line endings on untouched text fields).
    Content beyond line endings must be identical. Returns (ok, diff)."""
    b, a = row_by_id(initial_db, table, row_id), row_by_id(after_db, table, row_id)
    if b is None or a is None:
        return False, {"missing": True}
    diff = {}
    for k in b:
        if b[k] == a.get(k):
            continue
        if k in allowed_cols:
            diff[k] = (b[k], a[k])
            continue
        vb, va = str(b[k] or ""), str(a.get(k) or "")
        if vb.replace("\r\n", "\n") == va.replace("\r\n", "\n"):
            diff[k] = (b[k], a[k], "crlf-only")
            continue
        diff[k] = (b[k], a[k])
        return False, diff
    return True, diff


def check_row_edited_only_in(j: Judge, initial_db, after_db, table: str, row_id: int,
                             allowed_cols: Iterable[str], label: str = "") -> None:
    ok, diff = row_changed_only_in(initial_db, after_db, table, row_id, allowed_cols)
    j.check(f"{label or table}_row_{row_id}_edited_only_in_{list(allowed_cols)}", ok, f"diff={diff!r}")


def check_row_edited_only_in_crlf(j: Judge, initial_db, after_db, table: str, row_id: int,
                                  allowed_cols: Iterable[str], label: str = "") -> None:
    ok, diff = row_edited_only_in_with_crlf(initial_db, after_db, table, row_id, allowed_cols)
    j.check(f"{label or table}_row_{row_id}_edited_only_in_{list(allowed_cols)}_crlf_tolerant", ok, f"diff={diff!r}")

def bound_measure(text, label, expected, pattern, convert):
    labels = list(re.finditer(label, text, re.I))
    values = list(re.finditer(pattern, text, re.I))
    claims = []
    for match in labels:
        nearby = [(max(value.start() - match.end(), match.start() - value.end(), 0), value)
                  for value in values
                  if not re.search(r"[;\n]|(?<!\d)\.(?!\d)",
                                   text[min(value.end(), match.end()):max(value.start(), match.start())])]
        if nearby:
            distance, value = min(nearby, key=lambda item: item[0])
            if distance <= 80:
                claims.append(convert(value))
    return bool(claims) and all(value == expected for value in claims)


def money_claim(text, label, amount):
    return bound_measure(text, label, amount,
                         r"\$\s*([\d,]+(?:\.\d+)?)",
                         lambda m: float(m.group(1).replace(',', '')))
