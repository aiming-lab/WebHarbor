#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Amazon task verification.

Philosophy (same contract as the merriam_webster / phet_simulations exemplars):
DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / price containment against ground truth hardcoded in
     each verify_<n>.py (ground truth confirmed on the served mirror pages; the
     catalog is fixed by the seed DB and the mirror has no wall-clock content).
  4. DB state check: read-only tasks require the instance DB to be identical to
     its seed snapshot (anonymous carts are cookie-backed, so an honest run of
     any task in this task file leaves the DB untouched). DBs are fetched with
     docker cp from the site container (default $WH_CONTAINER or wh-ver-amazon),
     or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-amazon)
  --no_llm           accepted no-op (deterministic-only suite)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SITE = "amazon"
DB_FILENAME = "amazon_store.db"

TABLES = ("users", "categories", "products", "cart_items", "orders",
          "order_items", "wishlist_items", "reviews", "payment_methods",
          "saved_addresses", "returns", "return_items")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """Amazon--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{SITE.title()}--{m.group(1)}" if m else None


def load_run(run_dir):
    """Load and structurally validate the run package. Raises RunPackageError."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run_dir does not exist: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.exists():
        raise RunPackageError(f"missing trajectory.json under {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except Exception as e:
        raise RunPackageError(f"trajectory.json is not valid JSON: {e}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json must contain a JSON object")

    expected = expected_task_id()
    task_id = traj.get("task_id")
    if expected and task_id != expected:
        raise RunPackageError(f"task_id mismatch: expected {expected!r}, got {task_id!r}")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RunPackageError("task_id must be a non-empty string")

    start_url = traj.get("start_url") or ""
    if "/search" in start_url or "/product" in start_url:
        pass  # still the site origin; allowed
    if not re.match(r"^https?://", start_url):
        raise RunPackageError(f"start_url must be an http(s) URL, got {start_url!r}")

    shots_dir = d / "screenshots"
    if not shots_dir.is_dir():
        raise RunPackageError(f"missing screenshots/ directory under {d}")
    shots = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    if not shots:
        raise RunPackageError("no step_*.png screenshots under screenshots/")

    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunPackageError("trajectory must hold a non-empty steps list")

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise RunPackageError(f"step {i} is not an object")
        if not (s.get("url") or s.get("url_after")):
            raise RunPackageError(f"step {i} has no url / url_after")
        for field in ("screenshot_before", "screenshot_after"):
            name = s.get(field)
            if isinstance(name, str) and name:
                if Path(name).name not in shots:
                    raise RunPackageError(
                        f"step {i} references {field} {name!r} which is missing from screenshots/")

    traj["_run_dir"] = d
    traj["_shots"] = shots
    return traj


def load_run_checked(run_dir, judge):
    try:
        return load_run(run_dir)
    except RunPackageError as e:
        judge.check("run_package_valid", False, str(e))
        judge.emit()


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------- navigation
def step_urls(traj):
    """Every recorded step URL (before + after the action) in chronological order."""
    out = []
    for s in traj.get("steps", []):
        for field in ("url", "url_after"):
            u = s.get(field)
            if isinstance(u, str) and u:
                out.append(u)
    return out


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on recorded step URLs."""
    needle = substr.lower()
    return sum(1 for u in step_urls(traj) if needle in u.lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def visited_product(traj, slug):
    return navigated_to(traj, f"/product/{slug}")


def visited_root(traj):
    """True when some step URL is the bare site origin (the mirror homepage)."""
    return any(re.match(r"^https?://[^/]+/?$", u) for u in step_urls(traj))


def search_url_with(traj, must_have_all):
    """True when some visited URL is a /search (or /c/) page whose query string
    contains every required param substring (e.g. ['q=xbox', 'color=green'])."""
    for u in step_urls(traj):
        if "/search" not in u and "/c/" not in u:
            continue
        if all(m.lower() in u.lower() for m in must_have_all):
            return True
    return False


# ---------------------------------------------------------------- answer matching
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def price_in(final, price):
    """True when the answer mentions the given price, with the cents part when
    it is not integral: 64.99 matches '$64.99' / '64.99' / 'USD 64.99';
    179.00 matches '179.00', '$179', '179 dollars', or bare '179'."""
    f = norm(final)
    if abs(price - round(price)) > 1e-9:
        txt = f"{price:.2f}"
        alt = txt.replace(".", ",")
        return txt in f or alt in f or txt.rstrip("0").rstrip(".") in f
    whole = str(int(round(price)))
    return bool(re.search(r"(?<![\d.])" + whole + r"(?![\d])", f)) or f"{whole}.00" in f


def first_mention(final, tokens):
    """Index (in the normalized answer) of the earliest occurrence among tokens,
    or None when none of them appears. Used for ordering-sensitive answers."""
    f = norm(final)
    idxs = [f.find(norm(t)) for t in tokens if f.find(norm(t)) >= 0]
    return min(idxs) if idxs else None


def count_claim(final, number, word):
    """True when the answer claims `number` of `word`, tolerating up to three
    attributive words in between ('24 vibrant colors', '24 colors') or the
    number after the word ('colors: 24', 'colors — 24')."""
    f = norm(final)
    return bool(re.search(rf"(?<![\d.]){number}(?![\d])(\s+[a-z-]+){{0,3}}\s+{word}s?\b", f)) \
        or bool(re.search(rf"{word}s?[^.;]{{0,20}}(?<![\d.]){number}(?![\d])", f))


def mentions_percent_for(final, name_tokens, pct):
    """True when the answer mentions the product (all name tokens) together with
    the exact discount percentage (e.g. '-33%', '33% off')."""
    if not contains_all(final, name_tokens):
        return False
    f = norm(final)
    return bool(re.search(rf"(?<!\d){pct}\s?%", f))


def extract_color_count_claim(final):
    """Return the number the answer claims as the total color count, best-effort:
    looks for '<n> [attr] colors' / 'colors: <n>' / '<n> color options'."""
    f = norm(final)
    m = re.search(r"(\d+)(\s+[a-z]+){0,3}\s+colors?\b", f) or \
        re.search(r"colors?\s*[:=]?\s*(\d+)", f) or \
        re.search(r"(\d+)\s*color\s*options", f)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state)."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{DB_FILENAME}"
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip()}")
    return path


def resolve_db(arg, container, kind):
    if arg:
        return arg
    try:
        return fetch_db(container, kind)
    except Exception:
        return None  # caller FAILs the check that needs it


def db_fingerprint(db_path):
    """Content fingerprint of the benchmark tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in TABLES:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def read_only_run(initial_db, after_db):
    """True when the after-state DB is byte-for-row identical to the seed state.
    None when either DB is unavailable."""
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None
    return a == b


def db_table_rows(db_path, table):
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        try:
            return con.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.Error:
            return []
    finally:
        con.close()


def db_delta(initial_db, after_db, allowed_cart_products=(), allowed_wishlist_products=()):
    """Classify the DB delta of a run against the seed state.

    Returns (ok, detail): ok=True when the only differences are additions of
    cart_items / wishlist_items rows whose product_id is in the task's allowed
    product set — exactly the state change the task wording invites ("add to
    cart", "save"). Every other table must be identical; a modified or deleted
    existing row, or an added row for an unrelated product, is a violation.
    None when either DB is unavailable.
    """
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable"
    violations = []
    allowed_added = []
    allowed_cart = set(allowed_cart_products)
    allowed_wish = set(allowed_wishlist_products)
    for table in TABLES:
        before = db_table_rows(initial_db, table)
        after = db_table_rows(after_db, table)
        if before == after:
            continue
        bset = {repr(r) for r in before}
        aset = {repr(r) for r in after}
        added = [r for r in after if repr(r) not in bset]
        removed = [r for r in before if repr(r) not in aset]
        if removed:
            violations.append(f"{table}: {len(removed)} row(s) removed/changed")
        if not added:
            continue
        if table == "cart_items":
            for row in added:
                pid = row[2] if len(row) > 2 else None
                if pid in allowed_cart:
                    allowed_added.append(("cart_items", pid))
                else:
                    violations.append(
                        f"cart_items: added row for product_id={pid} (not an allowed product for this task)")
        elif table == "wishlist_items":
            for row in added:
                pid = row[2] if len(row) > 2 else None
                if pid in allowed_wish:
                    allowed_added.append(("wishlist_items", pid))
                else:
                    violations.append(
                        f"wishlist_items: added row for product_id={pid} (not an allowed product for this task)")
        else:
            violations.append(f"{table}: {len(added)} row(s) added (no table writes are allowed)")
    if violations:
        return False, "; ".join(violations)[:300]
    if allowed_added:
        return True, "db = seed + allowed cart/wishlist adds " + str(sorted(set(allowed_added)))
    return True, "db identical to seed"


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no-llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name   # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)


def parse_args():
    import simpleArgParser as sap

    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-amazon")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a, allowed_cart_products=(), allowed_wishlist_products=()):
    """Package gate + non-empty answer + DB-state check shared by every task.
    Returns (traj, final_answer). The DB check is strict read-only unless the
    task passes an allowed product set (cart/wishlist adds the task invites)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok, detail = db_delta(init, after, allowed_cart_products, allowed_wishlist_products)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa
