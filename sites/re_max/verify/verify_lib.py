#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for re_max task verification.

Same contract as the hardened reviewer suites (``sites/parkers/verify/verify_lib.py``,
``sites/merriam_webster/verify/verify_lib.py``). No LLM call is load-bearing;
every check is regex / token / SQLite after-state.

  1. Package identity: task_id matches, ``terminated`` with ``agent_done``,
     non-empty final answer, every recorded URL on the same loopback origin AND
     port as ``start_url``, every referenced screenshot a decodable PNG.
  2. Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
     on-site surfaces the task names — the city search-results page carrying
     the task's filter combination, the listing detail page for the task's
     home, the rental table + rental detail, the agent finder with the task's
     filter and the agent detail page, the office detail page, the advice
     article, the open-house state page, the site search, and the account
     surfaces (login, register, favorites, account, account edit).
  3. Answer check: affirmative token / phrase / amount / count matching against
     frozen ground truth that is HARDCODED in each ``verify_N.py`` (never in
     ``tasks.jsonl``).
  4. DB after-state: initial (seed) vs after (instance) SQLite snapshots.
     Read-only tasks require a row-identical database; stateful tasks require
     the exact allowed row delta and nothing else.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db, else
                       instance_seed from the container)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db, else live
                       instance DB from the container)
  --container NAME     docker container to fetch DBs from (default: $WH_CONTAINER or
                       wh-remax-review)
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

SITE = "re_max"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-remax-review")

# ------------------------------------------------------- frozen seed contract
TABLES = ("agents", "blog_posts", "favorites", "inquiries", "listing_alerts",
          "listings", "newsletter_subscribers", "offices", "rentals",
          "saved_searches", "users")
SEED_COUNTS = {"agents": 24, "blog_posts": 21, "favorites": 14, "inquiries": 2,
               "listing_alerts": 1, "listings": 431,
               "newsletter_subscribers": 0, "offices": 24, "rentals": 97,
               "saved_searches": 3, "users": 4}
# sha256 over sqlite_master (type, name, tbl_name, sql) of instance_seed/re_max.db.
SCHEMA_SHA256 = "445bcebb5571f01ffa391ce10dcb6aa8224a464dd862960d6d08bdf56afc4450"
# sha256 over every row of every table (ordered by the first two columns).
# r2 (c5ef103e): listing 286 gained the upstream HOA FEATURES facts section,
# so the row hash moved from the r1 value; schema + counts are unchanged and
# the seed is still build-time deterministic (PYTHONHASHSEED=0; python 3.11
# and 3.12 builds produce identical rows).
# audit r2 (2026-09-25): agent 5 (Wesley Hardin) title corrected to the
# upstream casing "Owner/Managing Broker" (r1 finding C-6); schema +
# counts unchanged, rows hash re-anchored.
SEED_ROWS_SHA256 = "10caa1d163a37fc493fc0822d61e10c59832701416f727bc86f41fc30c247a7b"

BENCHMARK_USERS = ("alice.j@test.com", "bob.c@test.com",
                   "carol.d@test.com", "david.k@test.com")
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
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
         .replace("–", "-").replace("—", "-").replace("−", "-"))
    return re.sub(r"\s+", " ", s).strip().lower()


# ------------------------------------------------------ re_max navigation gates
def nav_srp(traj, state, city, **filters):
    """City SRP visit carrying the task's filter combination (any subset match
    on the given params; a param the agent never set must not appear)."""
    city_slug = city.lower().replace(" ", "-")
    for u in site_urls(traj):
        path = normalized_url_path(u)
        if path != f"/{state}/{city_slug}-real-estate":
            continue
        q = _query_params(u)
        if all(str(v) in q.get(k, []) for k, v in filters.items()):
            return True
    return False


def nav_srp_any(traj, state, city):
    city_slug = city.lower().replace(" ", "-")
    return any(normalized_url_path(u) == f"/{state}/{city_slug}-real-estate"
               for u in site_urls(traj))


def nav_ldp(traj, listing_id):
    """Listing detail page for the given listing id (path ends /<id>)."""
    wanted = f"/{listing_id}"
    return any(normalized_url_path(u).endswith(wanted)
               and "home-details" in normalized_url_path(u)
               for u in site_urls(traj))


def nav_rental_detail(traj, rental_id):
    return any(normalized_url_path(u) == f"/rental-details/x/{rental_id}"
               or (normalized_url_path(u).startswith("/rental-details/")
                   and normalized_url_path(u).endswith(f"/{rental_id}"))
               for u in site_urls(traj))


def nav_agent_detail(traj, remax_id):
    return any(normalized_url_path(u).endswith(f"/{remax_id}")
               and "real-estate-agents" in normalized_url_path(u)
               for u in site_urls(traj))


def nav_office_detail(traj, remax_id):
    return any(normalized_url_path(u).endswith(f"/{remax_id}")
               and "/office/" in normalized_url_path(u)
               for u in site_urls(traj))


def nav_agents_filtered(traj, **filters):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/real-estate-agents":
            continue
        q = _query_params(u)
        if all(str(v) in q.get(k, []) for k, v in filters.items()):
            return True
    return False


def nav_offices_filtered(traj, **filters):
    """Office finder (/real-estate-offices) visit carrying the task's filter
    combination (e.g. language=Hindi)."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/real-estate-offices":
            continue
        q = _query_params(u)
        if all(str(v) in q.get(k, []) for k, v in filters.items()):
            return True
    return False


def nav_article(traj, slug):
    return navigated_to_path(traj, f"/advice/{slug}")


def nav_open_houses_state(traj, state):
    return navigated_to_path(traj, f"/open-houses/{state}")


def nav_state_page(traj, state):
    return navigated_to_path(traj, f"/homes-for-sale/{state}")


def nav_search_query(traj, tokens):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        q = " ".join(_query_params(u).get("q", [])).lower()
        if any(t in q for t in tokens):
            return True
    return False


def nav_rentals_table(traj):
    return navigated_to_path(traj, "/new-rentals") or navigated_to_path(traj, "/homes-for-rent")


def nav_luxury(traj):
    return navigated_to_path(traj, "/luxury")


def nav_login(traj):
    return navigated_to_path(traj, "/login")


def nav_register(traj):
    return navigated_to_path(traj, "/register")


def nav_favorites(traj):
    return navigated_to_path(traj, "/favorites")


def nav_account(traj):
    return navigated_to_path(traj, "/account")


def nav_account_edit(traj):
    return navigated_to_path(traj, "/account/edit")


# ---------------------------------------------------------------- answer matching
def _answer_tokens(answer):
    return normalize_text(answer)


def contains_phrase(answer, phrase):
    return normalize_text(phrase) in _answer_tokens(answer)


def contains_any_phrase(answer, phrases):
    return any(contains_phrase(answer, p) for p in phrases)


def contains_amount(answer, amount, tolerance=0.011):
    """$3,210 / 3,210 / 3210 — optional $ sign and thousands separators."""
    text = _answer_tokens(answer).replace("$", " ").replace("£", " ")
    wanted = float(amount)
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?\b", text):
        whole = m.group(1).replace(",", "")
        frac = m.group(2) or ""
        try:
            value = float(whole + ("." + frac if frac else ""))
        except ValueError:
            continue
        if abs(value - wanted) <= tolerance:
            return True
    return False


def contains_amount_range(answer, low, high):
    """Both endpoints of a $low - $high range appear (order-insensitive)."""
    return contains_amount(answer, low) and contains_amount(answer, high)


def contains_count(answer, n):
    text = _answer_tokens(answer)
    wanted = str(n)
    comma = f"{int(n):,}"
    for form in (wanted, comma):
        if re.search(rf"(?<!\d){re.escape(form)}(?!\d)", text):
            return True
    return False


def mentions_none_of(answer, phrase_list):
    return not any(contains_phrase(answer, p) for p in phrase_list)


def mentions_near(answer, anchor, phrase, window=160):
    """The phrase appears within `window` chars AFTER an occurrence of the
    anchor — binding a fact to the home/rental/agent it belongs to, so a
    swapped attribution ("home A's window quoted under home B") fails even
    though both strings appear somewhere in the answer."""
    text = normalize_text(answer)
    a = normalize_text(anchor)
    p = normalize_text(phrase)
    if not a or not p:
        return False
    start = 0
    while True:
        i = text.find(a, start)
        if i == -1:
            return False
        if p in text[i:i + len(a) + window]:
            return True
        start = i + 1


# ---------------------------------------------------------------- DB plumbing
def _connect(path):
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _docker_seed(container):
    out = Path(tempfile.mkdtemp(prefix="remax-verify-"))
    seed = out / "initial.db"
    subprocess.run(["docker", "cp",
                    f"{container}:/opt/WebSyn/re_max/instance_seed/re_max.db",
                    str(seed)], check=True, capture_output=True, timeout=120)
    return seed


def _docker_live(container):
    out = Path(tempfile.mkdtemp(prefix="remax-verify-"))
    live = out / "after.db"
    subprocess.run(["docker", "cp",
                    f"{container}:/opt/WebSyn/re_max/instance/re_max.db",
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
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
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
    """The initial DB must be the frozen seed (schema + counts + rows)."""
    judge.check(f"{label}_schema", schema_sha(db_path) == SCHEMA_SHA256,
                f"schema sha {schema_sha(db_path)[:12]}… != {SCHEMA_SHA256[:12]}…")
    counts = table_counts(db_path)
    drift = {t: (counts.get(t), SEED_COUNTS[t]) for t in SEED_COUNTS
             if counts.get(t) != SEED_COUNTS[t]}
    judge.check(f"{label}_counts", not drift, f"count drift={drift}")
    judge.check(f"{label}_rows", all_rows_sha(db_path) == SEED_ROWS_SHA256,
                "row hash mismatch")


def check_read_only(judge, initial_db, after_db):
    """After-state must be row-identical to the initial state."""
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


def removed_rows(after_db, initial_db, table, key):
    after = {r[key] for r in rows_of(after_db, table)}
    return [r for r in rows_of(initial_db, table) if r[key] not in after]


def user_by_email(db_path, email):
    for r in rows_of(db_path, "users"):
        if (r["email"] or "").lower() == email.lower():
            return r
    return None


def favorites_of(db_path, email):
    u = user_by_email(db_path, email)
    if not u:
        return []
    return sorted(r["listing_id"] for r in
                  rows_of(db_path, "favorites", "WHERE user_id = ?", (u["id"],)))


def check_only_tables_changed(judge, initial_db, after_db, allowed):
    """No table outside ``allowed`` may change (counts then rows)."""
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


def check_visited_path(judge, traj, name, path):
    judge.check(name, navigated_to_path(traj, path), f"required: {path}")


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
                          "reason": "usage: verify_N.py --run_dir DIR [--initial_db P] [--after_db P] [--container NAME]"}))
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
               "reason": "all checks passed" if judge.passed else "failed: " + ", ".join(judge.failed),
               "evidence": judge.evidence}
    print(json.dumps(verdict))
    sys.exit(0 if judge.passed else 1)
