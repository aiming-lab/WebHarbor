#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for OhioMeansJobs task
verification.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(``sites/megabus/verify/verify_lib.py``, ``sites/michaels/verify/verify_lib.py``).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the job-search engine (with the task's
     query/facet parameters), job detail pages, company profiles, the account
     area (register/login/saved jobs/saved searches/applications/resume/cover
     letters), the career quiz, county job-center lookup, the state-agency
     roster, news, the help center, the employer hub, the site search. A
     correct answer with no matching navigation is a memory-recall shortcut
     = FAIL.
  3. Answer check: token / phrase / count / date / amount matching against
     frozen ground truth that is HARDCODED in each ``verify_N.py`` (never in
     ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require every table row-identical; stateful tasks require
     the exact allowed row delta and nothing else (a registered user, an
     attached application, a saved-search create+delete pair, a resume skills
     update, a cover-letter delete+create pair, a career-quiz result row).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-omj-review)
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

SITE = "ohiomeansjobs"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-omj-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("applications", "career_plan_tasks", "career_quiz_results", "contact_messages",
          "cover_letters", "help_articles", "job_centers", "jobs", "news_items",
          "resumes", "saved_jobs", "saved_searches", "state_agencies", "users")
SEED_COUNTS = {"applications": 5, "career_plan_tasks": 11, "career_quiz_results": 0,
               "contact_messages": 0, "cover_letters": 9, "help_articles": 4,
               "job_centers": 89, "jobs": 160, "news_items": 10, "resumes": 4,
               "saved_jobs": 12, "saved_searches": 8, "state_agencies": 37, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/ohiomeansjobs.db.
SCHEMA_SHA256 = "8124a64fcd00425adbb96d6964a3b7865ecf6c7648493265a3c50ca6380bdd8a"
# sha256 over every seed row (table-canonical, ORDER BY all columns). The seed is
# built deterministically at image build time (PYTHONHASHSEED=0, frozen bcrypt
# hash, RNG_SEED=20260924 anchored to 2026-09-24) and a clean in-container
# rebuild reproduces it byte-for-byte.
SEED_ROWS_SHA256 = "83af2826638ec2e90e174841f73790d45cc521fff173c0eda739ee0acf1db6a2"
SEED_USERS = {  # email -> (id, name); identity columns never change
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


def navigated_to_path_any(traj, expected_paths):
    return any(navigated_to_path(traj, p) for p in expected_paths)


def navigated_jobs_search(traj, **params):
    """/jobs/search visit whose query string carries every required param=value."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/jobs/search":
            continue
        q = _query_params(u)
        ok = True
        for key, values in params.items():
            wanted = [str(v) for v in (values if isinstance(values, (list, tuple)) else [values])]
            if not any(str(q.get(key, [""])[0]) == str(w) or str(w) in q.get(key, []) for w in wanted):
                ok = False
                break
        if ok:
            return True
    return False


def navigated_job_detail(traj, jobid):
    return navigated_to_path(traj, f"/jobs/view/{jobid}")


def navigated_job_detail_any(traj, jobids):
    return any(navigated_job_detail(traj, j) for j in jobids)


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


def contains_amount(answer, amount, tolerance=0.011):
    """A money value like 85,000 (optionally prefixed with $) appears in the answer."""
    wanted = float(amount)
    for m in re.finditer(r"\$?\s*(\d+(?:[.,]\d+)*)", str(answer)):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if abs(value - wanted) <= tolerance:
            return True
    return False


def contains_count(answer, count):
    """The integer count appears as a standalone number (not part of a decimal).

    A trailing sentence period is allowed ("score of 2."), but a decimal
    separator followed by a digit is not ("2.5" is not the count 2).
    """
    text = str(answer)
    for m in re.finditer(r"(?<![\d.,\$])\d+(?!\d)(?![.,]\d)", text):
        if int(m.group(0)) == int(count):
            return True
    # comma-grouped thousands ("6,492") count as the integer 6492
    for m in re.finditer(r"(?<![\d.,\$])\d{1,3}(?:,\d{3})+(?!\d)", text):
        if int(m.group(0).replace(",", "")) == int(count):
            return True
    return False


def _standalone_counts(text):
    """Yield (start, end, value) for every standalone integer in the text."""
    for m in re.finditer(r"(?<![\d.,\$])\d+(?!\d)(?![.,]\d)", text):
        yield m.start(), m.end(), int(m.group(0))
    for m in re.finditer(r"(?<![\d.,\$])\d{1,3}(?:,\d{3})+(?!\d)", text):
        yield m.start(), m.end(), int(m.group(0).replace(",", ""))


def contains_count_near(answer, count, contexts, window=80):
    """The integer count appears standalone within `window` chars of any
    context token (e.g. the count 4 near "2022", or 2 near "part-time").

    Guards against a wrong count being rescued by the same integer
    appearing elsewhere in the answer (e.g. "Dec. 4" rescuing a wrong
    "4 news items in 2022"). Both the count and the context tokens are
    matched on the normalized text so whitespace/case never matter.
    """
    a = normalize_text(answer)
    wanted = [w for w in (normalize_text(c) for c in contexts) if w]
    for start, _end, value in _standalone_counts(a):
        if value != int(count):
            continue
        for w in wanted:
            idx = 0
            while True:
                j = a.find(w, idx)
                if j == -1:
                    break
                if abs(j - start) <= window + len(w):
                    return True
                idx = j + 1
    return False


def contains_date(answer, iso_date):
    """A date matches as ISO (2026-09-24) or US long (September 24, 2026) style."""
    y, m, d = iso_date.split("-")
    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]
    variants = {iso_date, f"{months[int(m) - 1]} {int(d)}, {y}",
                f"{months[int(m) - 1][:3]} {int(d)}, {y}", f"{int(d)} {months[int(m) - 1]} {y}"}
    a = normalize_text(answer)
    return any(normalize_text(v) in a for v in variants)


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
        raise ValueError("initial_db is not the frozen ohiomeansjobs seed (rows sha mismatch)")
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
                    "both initial (seed) and after (instance) ohiomeansjobs database snapshots are required")
    try:
        validate_snapshot_contract(initial_db, after_db)
    except (OSError, sqlite3.Error, ValueError) as exc:
        fail_closed(task_id, "snapshot_contract_invalid", str(exc))
    return str(initial_db), str(after_db)


# ---------------------------------------------------------------- omj-specific helpers
def user_by_email(db_path, email):
    rows = db_query(db_path, "SELECT * FROM users WHERE lower(email) = lower(?) LIMIT 1", (email,))
    return rows[0] if rows else None


def job_by_id(db_path, jobid):
    rows = db_query(db_path, "SELECT * FROM jobs WHERE jobid = ? LIMIT 1", (str(jobid),))
    return rows[0] if rows else None


def added_users(after_db, initial_db):
    init = {r["email"].lower() for r in db_query(initial_db, "SELECT email FROM users")}
    added = []
    for r in db_query(after_db, "SELECT * FROM users ORDER BY id"):
        if r["email"].lower() not in init:
            added.append(r)
    return added


def added_applications(after_db, initial_db):
    init = {(r["user_id"], r["job_id"]) for r in
            db_query(initial_db, "SELECT user_id, job_id FROM applications")}
    added = []
    for r in db_query(after_db, "SELECT * FROM applications ORDER BY id"):
        if (r["user_id"], r["job_id"]) not in init:
            added.append(r)
    return added


def removed_saved_jobs(after_db, initial_db):
    init = {(r["user_id"], r["job_id"]) for r in
            db_query(initial_db, "SELECT user_id, job_id FROM saved_jobs")}
    after = {(r["user_id"], r["job_id"]) for r in
             db_query(after_db, "SELECT user_id, job_id FROM saved_jobs")}
    gone = init - after
    out = []
    for uid, jid in gone:
        row = db_query(initial_db, "SELECT * FROM saved_jobs WHERE user_id=? AND job_id=?",
                      (uid, jid))
        if row:
            out.append(row[0])
    return out


def added_saved_searches(after_db, initial_db):
    init = {(r["user_id"], r["name"]) for r in
            db_query(initial_db, "SELECT user_id, name FROM saved_searches")}
    added = []
    for r in db_query(after_db, "SELECT * FROM saved_searches ORDER BY id"):
        if (r["user_id"], r["name"]) not in init:
            added.append(r)
    return added


def removed_saved_searches(after_db, initial_db):
    init = {(r["user_id"], r["name"]) for r in
            db_query(initial_db, "SELECT user_id, name FROM saved_searches")}
    after = {(r["user_id"], r["name"]) for r in
             db_query(after_db, "SELECT user_id, name FROM saved_searches")}
    gone = init - after
    out = []
    for uid, name in gone:
        row = db_query(initial_db, "SELECT * FROM saved_searches WHERE user_id=? AND name=?",
                       (uid, name))
        if row:
            out.append(row[0])
    return out


def cover_letters_of(db_path, user_id):
    return db_query(db_path, "SELECT * FROM cover_letters WHERE user_id = ? ORDER BY id",
                    (user_id,))


def resume_of(db_path, user_id):
    rows = db_query(db_path, "SELECT * FROM resumes WHERE user_id = ? LIMIT 1", (user_id,))
    return rows[0] if rows else None


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
    judge.check("visited_login_page", navigated_to_path(traj, "/account/login"),
                "required_path=/account/login")
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
