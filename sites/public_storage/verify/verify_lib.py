#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for Public Storage tasks.

Philosophy: DETERMINISTIC FIRST — same contract as the hardened reviewer
suites (sites/porsche/verify/verify_lib.py, sites/mta/verify/verify_lib.py).
No LLM call is load-bearing; every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened
     the on-site surfaces the task names — the ZIP search results page
     (/self-storage-search/<slug>, with the task's type/size/sort filters),
     the facility detail pages (/self-storage-<state>-<city>/<id>.html), the
     Hold Now form for the exact unit (/reservation/hold/<unit_id>), the
     reservation confirmation page, the size-guide hub and the task's FAQ
     page, the storage-type and storage-solutions pages, the blog article,
     the help-center topics, the login/register/account pages, and the
     bill-pay pages. A correct answer with no matching navigation is a
     memory-recall shortcut = FAIL.
  3. Answer check: affirmative token / phrase / amount / count / code
     matching against frozen ground truth that is HARDCODED in each
     ``verify_N.py`` (never in ``tasks.jsonl``). Generated values the agent
     cannot know in advance (reservation codes, payment confirmation numbers)
     are matched against the DB after-state instead of a hardcoded literal.
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require a row-identical database; stateful tasks
     require the exact allowed row delta and nothing else (one reservation
     row with the task's unit/facility/contact/move-in data, one payment row
     with the charged amount, one user row for the registration task, or the
     profile edit on the named benchmark account).

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-public-storage-review)
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
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

SITE = "public_storage"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-public-storage-review")

# ---------------------------------------------------------------- frozen seed contract
TABLES = ("blog_articles", "facilities", "faq_entries", "help_topics", "payments",
          "rentals", "reservations", "reviews", "saved_facilities", "site_copy",
          "size_faqs", "units", "users", "zip_results")
SEED_COUNTS = {"blog_articles": 38, "facilities": 140, "faq_entries": 10,
               "help_topics": 6, "payments": 0, "rentals": 4, "reservations": 4,
               "reviews": 1395, "saved_facilities": 8, "site_copy": 22,
               "size_faqs": 99, "units": 2135, "users": 4, "zip_results": 345}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/public_storage.db
SCHEMA_SHA256 = "855e56b78f155259c882b224c293bd61fd31d13646f7658bf1d9a24a775f348c"
# sha256 over every row of every table (ordered by the first two columns).
SEED_ROWS_SHA256 = "ab0c76b3a17bcac13cee09ddb1620a7eda69a98e54fbe83aedef50cd4958cd6f"

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


def navigated_zip_search(traj, slug_needle, **filters):
    """/self-storage-search/<slug> visit (or the param form) with optional
    type/sz/sort filters. ``slug_needle`` matches the captured slug (e.g.
    'austin-tx-78704' or just 'denver-co')."""
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if path != "/self-storage-search" and not path.startswith("/self-storage-search/"):
            continue
        if slug_needle not in path and slug_needle not in unquote(urlparse(u).query or ""):
            continue
        if not filters:
            return True
        q = _query_params(u)
        if all(str(v) in q.get(k, []) for k, v in filters.items()):
            return True
    return False


def navigated_facility(traj, facility_id):
    """Facility detail page /self-storage-<state>-<city>/<id>.html for the id."""
    suffix = f"/{int(facility_id)}.html"
    return any(normalized_url_path(u).endswith(suffix)
               and normalized_url_path(u).startswith("/self-storage-")
               and normalized_url_path(u) != f"/self-storage-{int(facility_id)}"
               for u in site_urls(traj))


def navigated_city_page(traj, city_slug):
    return navigated_to_path(traj, f"/self-storage-{city_slug}")


def navigated_hold_form(traj, unit_id):
    return navigated_to_path(traj, f"/reservation/hold/{unit_id}")


def navigated_confirmation(traj):
    return any(normalized_url_path(u).startswith("/reservation/confirmation/")
               for u in site_urls(traj))


def navigated_access_reservation(traj, times=1):
    return sum(1 for u in site_urls(traj)
               if normalized_url_path(u) == "/access-reservation") >= times


def navigated_sign_in(traj):
    return navigated_to_path(traj, "/lease/sign-elease")


def navigated_register(traj):
    return navigated_to_path(traj, "/myaccount/identity/create-account")


def navigated_account(traj):
    return navigated_to_path(traj, "/myaccount")


def navigated_account_edit(traj):
    return navigated_to_path(traj, "/myaccount/edit")


def navigated_bill_pay_login(traj):
    return navigated_to_path(traj, "/simplified/bill-pay/login")


def navigated_bill_pay(traj):
    return navigated_to_path(traj, "/simplified/bill-pay")


def navigated_size_guide(traj):
    return navigated_to_path(traj, "/size-guide")


def navigated_size_faq(traj, slug):
    return any(normalized_url_path(u).startswith(f"/size-guide/{slug}/")
               for u in site_urls(traj))


def navigated_type_page(traj, slug):
    return navigated_to_path(traj, f"/{slug}")


def navigated_solution(traj, slug):
    return navigated_to_path(traj, f"/storage-solutions/{slug}")


def navigated_help_topic(traj, slug):
    return navigated_to_path(traj, f"/help/{slug}")


def navigated_help_home(traj):
    return navigated_to_path_any(traj, ["/help", "/help/"])


def navigated_blog_index(traj):
    return navigated_to_path(traj, "/blog")


def navigated_blog_article(traj, slug):
    return any(normalized_url_path(u).endswith(f"/{slug}.html")
               and normalized_url_path(u).startswith("/blog/")
               for u in site_urls(traj))


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


def normalize_text(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = (s.replace("\u2019", "'").replace("\u2018", "'")
         .replace("\u201c", '"').replace("\u201d", '"')
         .replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-"))
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------- answer matching
def contains_phrase(answer, phrase):
    return normalize_text(phrase) in normalize_text(answer)


def contains_any_phrase(answer, phrases):
    return any(contains_phrase(answer, p) for p in phrases)


def contains_amount(answer, amount, tolerance=0.011):
    """$45 / 45 / $45.00 / 45.00 — optional $ and thousands separators."""
    text = normalize_text(answer)
    wanted = float(amount)
    for m in re.finditer(r"\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?", text):
        whole = m.group(1).replace(",", "")
        frac = m.group(2) or ""
        try:
            value = float(whole + ("." + frac if frac else ""))
        except ValueError:
            continue
        if abs(value - wanted) <= tolerance:
            return True
    return False


def contains_count(answer, n):
    text = normalize_text(answer)
    wanted = str(n)
    comma = f"{int(n):,}"
    for form in (wanted, comma):
        if re.search(rf"(?<!\d){re.escape(form)}(?!\d)", text):
            return True
    return False


def contains_reservation_code(answer):
    return bool(re.search(r"ps-\d{7}", normalize_text(answer)))


def contains_payment_code(answer):
    return bool(re.search(r"ps-pay-\d{6}", normalize_text(answer)))


def contains_ref(answer, ref):
    return normalize_text(ref) in normalize_text(answer)


def mentions_none_of(answer, phrase_list):
    return not any(contains_phrase(answer, p) for p in phrase_list)


# ---------------------------------------------------------------- DB plumbing
def _connect(path):
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _docker_seed(container):
    out = Path(tempfile.mkdtemp(prefix="ps-verify-"))
    seed = out / "initial.db"
    subprocess.run(["docker", "cp",
                    f"{container}:/opt/WebSyn/public_storage/instance_seed/public_storage.db",
                    str(seed)], check=True, capture_output=True, timeout=120)
    return seed


def _docker_live(container):
    out = Path(tempfile.mkdtemp(prefix="ps-verify-"))
    live = out / "after.db"
    subprocess.run(["docker", "cp",
                    f"{container}:/opt/WebSyn/public_storage/instance/public_storage.db",
                    str(live)], check=True, capture_output=True, timeout=120)
    return live


def resolve_dbs(run_dir, initial_db, after_db, container):
    d = Path(run_dir)
    if initial_db is None:
        cand = d / "initial.db"
        initial_db = cand if cand.is_file() else _docker_seed(container)
    if after_db is None:
        cand = d / "after.db"
        after_db = cand if cand.is_file() else _docker_live(container)
    return Path(initial_db), Path(after_db)


def table_counts(db_path):
    con = _connect(db_path)
    try:
        out = {}
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out
    finally:
        con.close()


def schema_sha(db_path):
    con = _connect(db_path)
    try:
        h = hashlib.sha256()
        for r in con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master "
                             "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"):
            h.update(repr(r).encode())
        return h.hexdigest()
    finally:
        con.close()


def all_rows_sha(db_path):
    con = _connect(db_path)
    try:
        h = hashlib.sha256()
        for t in TABLES:
            for r in con.execute(f"SELECT * FROM {t} ORDER BY 1, 2"):
                h.update(repr(r).encode())
        return h.hexdigest()
    finally:
        con.close()


def check_seed_contract(judge, db_path, label="initial_db"):
    judge.check(f"{label}_schema", schema_sha(db_path) == SCHEMA_SHA256,
                f"schema sha {schema_sha(db_path)[:12]}… != {SCHEMA_SHA256[:12]}…")
    counts = table_counts(db_path)
    drift = {t: (counts.get(t), SEED_COUNTS[t]) for t in SEED_COUNTS
             if counts.get(t) != SEED_COUNTS[t]}
    judge.check(f"{label}_counts", not drift, f"count drift={drift}")
    judge.check(f"{label}_rows", all_rows_sha(db_path) == SEED_ROWS_SHA256,
                "row hash mismatch")


def check_read_only(judge, initial_db, after_db):
    judge.check("read_only_counts", table_counts(after_db) == table_counts(initial_db),
                f"counts differ: {table_counts(after_db)} vs {table_counts(initial_db)}")
    judge.check("read_only_rows", all_rows_sha(after_db) == all_rows_sha(initial_db),
                "rows differ")


def rows_of(db_path, table, where="", args=()):
    con = _connect(db_path)
    try:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        q = f"SELECT * FROM {table} {where}"
        return [dict(zip(cols, r)) for r in con.execute(q, args)]
    finally:
        con.close()


def added_rows(after_db, initial_db, table, key):
    before = {r[key] for r in rows_of(initial_db, table)}
    return [r for r in rows_of(after_db, table) if r[key] not in before]


def user_by_email(db_path, email):
    for r in rows_of(db_path, "users"):
        if (r["email"] or "").lower() == email.lower():
            return r
    return None


def reservation_by_code(db_path, code):
    for r in rows_of(db_path, "reservations"):
        if (r["code"] or "").upper() == str(code).upper():
            return r
    return None


def unit_row(db_path, unit_id):
    for r in rows_of(db_path, "units"):
        if r["unit_id"] == unit_id:
            return r
    return None


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    ci, ca = table_counts(initial_db), table_counts(after_db)
    changed = {t for t in ci if ci[t] != ca.get(t)}
    unexpected = changed - set(allowed)
    judge.check("no_unexpected_table_count_change", not unexpected,
                f"unexpected count changes: {sorted(unexpected)}")
    for t in TABLES:
        if t in unexpected or t in allowed:
            continue
        if rows_of(initial_db, t) != rows_of(after_db, t):
            judge.check(f"table_{t}_unchanged", False, f"{t} rows changed without permission")


# ---------------------------------------------------------------- verdict plumbing
class Judge:
    def __init__(self):
        self.evidence = []
        self.failed = []

    def check(self, name, ok, detail=""):
        ok = bool(ok)
        self.evidence.append({"check": name, "ok": ok, "detail": str(detail)[:400]})
        if not ok:
            self.failed.append(name)

    @property
    def passed(self):
        return not self.failed


def _png_ok(path):
    try:
        head = Path(path).read_bytes()[:8]
    except OSError:
        return False
    return head == b"\x89PNG\r\n\x1a\n"


def check_trajectory_identity(judge, traj, task_id):
    judge.check("task_id", traj.get("task_id") == task_id,
                f"task_id={traj.get('task_id')!r}, expected {task_id!r}")
    judge.check("terminated_agent_done",
                bool(traj.get("terminated")) and traj.get("termination_reason") == "agent_done",
                f"terminated={traj.get('terminated')!r} reason={traj.get('termination_reason')!r}")
    answer = final_answer(traj)
    judge.check("final_answer_nonempty", len(answer) >= 10, f"answer len={len(answer)}")
    urls = trajectory_urls(traj)
    start = traj.get("start_url")
    judge.check("start_url_present", bool(start), "missing start_url")
    if start:
        p = urlparse(str(start))
        origin = (p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80))
        bad = []
        for u in urls:
            q = urlparse(str(u))
            if not is_site_url(u):
                bad.append(u)
                continue
            if (q.scheme, q.hostname, q.port or (443 if q.scheme == "https" else 80)) != origin:
                bad.append(u)
        judge.check("same_origin_urls", not bad, f"off-origin urls: {bad[:3]}")
    shots = traj.get("_shots") or {}
    judge.check("screenshots_present", len(shots) >= 1, f"shots={len(shots)}")
    bad_shots = [n for n, p in list(shots.items())[:50] if not _png_ok(p)]
    judge.check("screenshots_decode_png", not bad_shots, f"bad: {bad_shots[:3]}")


def run_verifier(task_id, run_checks):
    ap = sys.argv
    args = {"--run_dir": None, "--initial_db": None, "--after_db": None, "--container": None}
    i = 1
    while i < len(ap):
        if ap[i] in args:
            args[ap[i]] = ap[i + 1]
            i += 2
        else:
            i += 1
    if not args["--run_dir"]:
        print(json.dumps({"task_id": task_id, "pass": False,
                          "reason": "usage: verify_N.py --run_dir DIR "
                                    "[--initial_db P] [--after_db P] [--container NAME]"}))
        sys.exit(2)
    container = args["--container"] or DEFAULT_CONTAINER
    judge = Judge()
    try:
        traj = load_run(args["--run_dir"])
        initial_db, after_db = resolve_dbs(args["--run_dir"], args["--initial_db"],
                                           args["--after_db"], container)
        run_checks(judge, traj, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 — fail closed on any infra error
        print(json.dumps({"task_id": task_id, "pass": False,
                          "reason": f"infra_error: {type(exc).__name__}: {exc}",
                          "evidence": judge.evidence}))
        sys.exit(1)
    verdict = {"task_id": task_id, "pass": judge.passed,
               "reason": "all checks passed" if judge.passed
                         else "failed: " + ", ".join(judge.failed),
               "evidence": judge.evidence}
    print(json.dumps(verdict))
    sys.exit(0 if judge.passed else 1)
