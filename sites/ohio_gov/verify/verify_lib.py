#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for Ohio.gov task grading.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/megabus/verify/verify_lib.py``, ``sites/michaels/verify/verify_lib.py``).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the Licenses & Permits directory (with
     the task's query), the State Directory / Phone Search / FAQ / Assistant
     surfaces, the news list + article pages, resource detail pages, the search
     tabs, and the account area for the stateful chains. A correct answer with
     no matching navigation is a memory-recall shortcut = FAIL.
  3. Answer check: phrase / token / count matching against frozen ground truth
     that is HARDCODED in each ``verify_N.py`` (never in ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require every table row-identical; stateful tasks require
     the exact allowed delta and nothing else (a saved-resource toggle set, a
     created user row with its profile fields, a travel-guide request row, a
     scam-report row, an added alert-subscription row, an updated user row).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed fetched from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB fetched from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-ohio-gov-review)
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

SITE = "ohio_gov"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-ohio-gov-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("site_content", "agencies", "alert_items", "alert_subscriptions", "assistant_queries",
          "contact_messages", "faq_categories", "faqs", "licenses", "news_articles",
          "phone_entries", "resources", "saved_resources", "scam_reports", "topic_hubs",
          "travel_guide_requests", "users")
SEED_COUNTS = {"site_content": 2, "agencies": 190, "alert_items": 4, "alert_subscriptions": 4,
               "assistant_queries": 0, "contact_messages": 0, "faq_categories": 23,
               "faqs": 119, "licenses": 272, "news_articles": 14, "phone_entries": 179,
               "resources": 242, "saved_resources": 17, "scam_reports": 1,
               "topic_hubs": 31, "travel_guide_requests": 1, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/ohio_gov.db,
# rebuilt deterministically at image build time (PYTHONHASHSEED=0) from the tracked
# data snapshot. Reproduced independently during review (in-container rebuild md5
# 16563ff30f7fceaada12f9f1ab7e0b22).
SCHEMA_SHA256 = "07b886756a3e5ce942fe89842cd9739b0f9997102caddcb871ea1cc226d90dcc"
# sha256 over every seed row (table-canonical, ORDER BY all columns).
SEED_ROWS_SHA256 = "9c42f9da1926c221bc59993c17a41610766398f2d2382219351af38fea8658b0"
SEED_USERS = {  # email -> (id, username); identity columns never change
    "alice.j@test.com": (1, "alice_j"),
    "bob.c@test.com": (2, "bob_c"),
    "carol.d@test.com": (3, "carol_d"),
    "david.k@test.com": (4, "david_k"),
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
            parse_qs(urlparse(url).query, keep_blank_values=True).items()}


def navigated_to(traj, substr, times=1):
    return sum(1 for u in site_urls(traj) if substr in u) >= times


def navigated_to_path(traj, expected_path):
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(u) == expected for u in site_urls(traj))


def navigated_to_path_times(traj, expected_path, times=2):
    expected = normalized_url_path(expected_path)
    return sum(1 for u in site_urls(traj) if normalized_url_path(u) == expected) >= times


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def navigated_with_query(traj, path, param, value_substr, casefold=True):
    """A visit to `path` whose `param` query value contains value_substr."""
    wanted = str(value_substr).casefold() if casefold else str(value_substr)
    for u in site_urls(traj):
        if normalized_url_path(u) != normalized_url_path(path):
            continue
        for v in _query_params(u).get(param, []):
            if (v.casefold() if casefold else v).find(wanted) >= 0:
                return True
    return False


def entered_identity(traj, expected):
    """The expected string appears in an input step (case-insensitive)."""
    wanted = normalize_text(expected)
    for step in traj.get("steps") or []:
        if not isinstance(step, dict) or step.get("action") not in INPUT_ACTIONS:
            continue
        params = step.get("params") or {}
        for v in (params.get("text"), params.get("value")):
            if v is not None and wanted in normalize_text(str(v)):
                return True
    return False


def input_texts(traj):
    out = []
    for step in traj.get("steps") or []:
        if isinstance(step, dict) and step.get("action") in INPUT_ACTIONS:
            params = step.get("params") or {}
            for v in (params.get("text"), params.get("value")):
                if v is not None:
                    out.append(str(v))
    return out


def normalize_text(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-").replace("−", "-"))
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------- answer matching
def contains_all(answer, tokens):
    a = normalize_text(answer)
    return all(normalize_text(t) in a for t in tokens)


def contains_any(answer, tokens):
    a = normalize_text(answer)
    return any(normalize_text(t) in a for t in tokens)


def contains_phrase(answer, phrase):
    return normalize_text(phrase) in normalize_text(answer)


def contains_count(answer, count):
    """The integer count appears as a standalone number (not part of a decimal)."""
    for m in re.finditer(r"(?<![\d.,\$])\d+(?![\d.,])", str(answer)):
        if int(m.group(0)) == int(count):
            return True
    return False


def contains_phone(answer, digits):
    """A phone number matches on its last 7 digits (area codes/format vary)."""
    wanted = re.sub(r"\D", "", str(digits))[-7:]
    observed = re.sub(r"\D", "", str(answer))
    return wanted in observed


# ---------------------------------------------------------------- snapshots
def db_query(db_path, sql, params=()):
    con = sqlite3.connect(str(db_path))
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def resolve_db(path, container, which):
    if path:
        p = Path(path)
        return p if p.is_file() else None
    cache = Path(tempfile.gettempdir()) / f"{SITE}_verify_{which}.db"
    if cache.is_file():
        return cache
    try:
        subprocess.run(["docker", "cp",
                        f"{container}:/opt/WebSyn/{SITE}/{which}/{SITE}.db", str(cache)],
                       check=True, capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    return cache if cache.is_file() else None


def schema_sha(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master "
                           "ORDER BY type, name").fetchall()
        h = hashlib.sha256()
        for r in rows:
            h.update(repr(tuple(r)).encode())
        return h.hexdigest()
    finally:
        con.close()


def rows_sha(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        h = hashlib.sha256()
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in names:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            order = ", ".join(f'"{c}"' for c in cols)
            for row in con.execute(f'SELECT * FROM "{t}" ORDER BY {order}'):
                h.update(repr(tuple(row)).encode())
        return h.hexdigest()
    finally:
        con.close()


def table_counts(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        out = {}
        for t in TABLES:
            out[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        return out
    finally:
        con.close()


def validate_snapshot_contract(initial_db, after_db):
    if schema_sha(initial_db) != SCHEMA_SHA256:
        raise ValueError(f"initial_db schema sha mismatch: {schema_sha(initial_db)}")
    counts = table_counts(initial_db)
    if counts != SEED_COUNTS:
        raise ValueError(f"initial_db table counts mismatch: {counts!r}")
    if rows_sha(initial_db) != SEED_ROWS_SHA256:
        raise ValueError("initial_db is not the frozen ohio_gov seed (rows sha mismatch)")
    if schema_sha(after_db) != SCHEMA_SHA256:
        raise ValueError(f"after_db schema sha mismatch: {schema_sha(after_db)}")


def changed_tables(initial_db, after_db, tables=None):
    con_i = sqlite3.connect(str(initial_db))
    con_a = sqlite3.connect(str(after_db))
    try:
        names = tuple(tables) if tables else TABLES
        changed = []
        for t in names:
            cols = [r[1] for r in con_i.execute(f'PRAGMA table_info("{t}")')]
            order = ", ".join(f'"{c}"' for c in cols) or "1"
            ri = con_i.execute(f'SELECT * FROM "{t}" ORDER BY {order}').fetchall()
            ra = con_a.execute(f'SELECT * FROM "{t}" ORDER BY {order}').fetchall()
            if ri != ra:
                changed.append(t)
        return changed
    finally:
        con_i.close()
        con_a.close()


def resolve_snapshots(args, task_id):
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(task_id, "database_unavailable",
                    "both initial (seed) and after (instance) ohio_gov database "
                    "snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- ohio_gov-specific helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return rows[0] if rows else None


def added_users(after_db, initial_db):
    init = {r["email"].lower() for r in db_query(initial_db, "SELECT email FROM users")}
    added = []
    for r in db_query(after_db, "SELECT * FROM users ORDER BY id"):
        if r["email"].lower() not in init:
            added.append(r)
    return added


def saved_slugs(db_path, user_id):
    """Slugs of the user's saved resources, in saved order (created_at, id)."""
    return [r["slug"] for r in db_query(
        db_path,
        "SELECT r.slug FROM saved_resources sr JOIN resources r ON r.id = sr.resource_id "
        "WHERE sr.user_id = ? ORDER BY sr.created_at, sr.id", (user_id,))]


def subscriptions_of(db_path, user_id):
    return db_query(db_path, "SELECT * FROM alert_subscriptions WHERE user_id = ? "
                             "ORDER BY id", (user_id,))


def added_travel_guide_requests(after_db, initial_db):
    init_ids = {r["id"] for r in db_query(initial_db, "SELECT id FROM travel_guide_requests")}
    return [r for r in db_query(after_db, "SELECT * FROM travel_guide_requests ORDER BY id")
            if r["id"] not in init_ids]


def added_scam_reports(after_db, initial_db):
    init_ids = {r["id"] for r in db_query(initial_db, "SELECT id FROM scam_reports")}
    return [r for r in db_query(after_db, "SELECT * FROM scam_reports ORDER BY id")
            if r["id"] not in init_ids]


# ---------------------------------------------------------------- judge + CLI
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
                self.reason = name
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


@dataclass
class VerifyArgs:
    run_dir: str = ""
    initial_db: str = ""
    after_db: str = ""
    container: str = ""
    no_llm: str = "False"

    def post_process(self):
        if not self.container:
            self.container = DEFAULT_CONTAINER
        if self.run_dir:
            run = Path(self.run_dir)
            if not self.initial_db and (run / "initial.db").is_file():
                self.initial_db = str(run / "initial.db")
            if not self.after_db and (run / "after.db").is_file():
                self.after_db = str(run / "after.db")


def parse_args():
    try:
        import simpleArgParser as sap  # the agent_demo env; boolean flags take a value
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
        check_precise_delta(judge, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(task_id, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


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
        from PIL import Image  # available in the agent_demo env
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
    judge.check("visited_login_page", navigated_to_path(traj, "/login"),
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
    others = tuple(t for t in TABLES if t not in set(allowed))
    changed = changed_tables(initial_db, after_db, others)
    return judge.check("no_collateral_writes", not changed,
                       f"tables_outside_allowed={list(others)!r}, changed={changed!r}")


STATE_RULES = {6: {'saved_resources': [1, [], [], 2]}, 7: {'users': [None, [], [], 1]}, 8: {'travel_guide_requests': [None, [], [], 2]}, 9: {'scam_reports': [None, [], [], 1]}, 10: {'alert_subscriptions': [2, [], [], 2]}, 18: {'users': [3, ['phone', 'city'], [], 0]}}


def check_precise_delta(judge, initial_db, after_db):
    """Preserve old rows and other owners, including inside mutable tables."""
    rules = STATE_RULES.get(int(judge.task_id.rsplit('--', 1)[1]), {})
    for table in TABLES:
        before = [dict(r) for r in db_query(initial_db, f'SELECT * FROM "{table}"')]
        after = [dict(r) for r in db_query(after_db, f'SELECT * FROM "{table}"')]
        if table not in rules:
            judge.check('preserved_' + table, before == after, 'unchanged table')
            continue
        owner, fields, deletion, new_count = rules[table]
        old = {r['id']: r for r in before};new = {r['id']: r for r in after}
        def owned(r):
            return owner is None or r.get('user_id', r.get('id') if table == 'users' else None) == owner
        deleted = []
        for pk, row in old.items():
            if pk not in new:
                permitted = bool(deletion) and owned(row) and row.get(deletion[0]) == deletion[1]
                judge.check('allowed_delete_' + table, permitted, f'id={pk}')
                deleted.append(pk)
            else:
                changed = {k for k in row if row[k] != new[pk][k]}
                judge.check('preserved_row_' + table, not changed or (owned(row) and changed <= set(fields)), f'id={pk}, changed={sorted(changed)}')
        judge.check('deletion_count_' + table, len(deleted) == (1 if deletion else 0), str(deleted))
        added = [r for pk, r in new.items() if pk not in old]
        judge.check('addition_count_' + table, len(added) == new_count, f'expected={new_count}, observed={len(added)}')
        judge.check('addition_owner_' + table, all(owned(r) for r in added), 'requested account only')
