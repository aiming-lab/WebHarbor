#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Raising Cane's task verification.

Philosophy: DETERMINISTIC FIRST, no LLM.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page; a correct answer with no matching
     navigation is a memory-recall shortcut = FAIL.
  2. DB after-state check (stateful tasks): query the SQLite instance DB
     directly — the strongest deterministic signal (placed order rows, gift
     card balances, points, cancelled status, profile edits).
  3. Answer check: exact / regex / token-containment against frozen ground
     truth hardcoded in each verifier.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH   after-state  SQLite DB (default: live instance DB from container)
  --container NAME  docker container to fetch DBs from (default: $WH_CONTAINER or wh-rc-review)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SITE = "raising_canes"

# ---------------------------------------------------------------- trajectory


def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))}
    return traj


def step_urls(traj):
    return [s.get("url", "") for s in traj.get("steps", [])]


def navigated_to(traj, substr, times=1):
    """At least `times` trajectory steps have a URL containing substr."""
    return sum(1 for u in step_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


def page_text_containing(traj, substr):
    """Full page_text of the first step whose URL contains substr (else '')."""
    for s in traj.get("steps", []):
        if substr in s.get("url", ""):
            return s.get("page_text") or s.get("observed_text") or ""
    return ""


# ---------------------------------------------------------------- answer match


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def answer_equals(final, expected):
    return norm(final) == norm(expected)


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def contains_money(final, amount):
    """Answer contains the dollar amount in any common rendering ($329.08 / 329.08 / $329,08)."""
    f = norm(final)
    a = f"{amount:.2f}"
    plain = a.replace(",", "")
    comma = f"{amount:,.2f}"
    return (f"${plain}" in f) or (f"${comma}" in f) or re.search(
        rf"(?<![0-9.]){re.escape(plain)}(?![0-9])", f) is not None


def contains_order_number(final, prefix="RC-"):
    """Answer mentions an order number with the given prefix (RC-100240, GEAR-4504)."""
    return re.search(rf"{re.escape(prefix)}\d+", final or "") is not None


def contains_number(final, number):
    f = norm(final)
    return re.search(rf"(?<![0-9.]){re.escape(str(number))}(?![0-9])", f) is not None


# ---------------------------------------------------------------- DB state


def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state). docker cp."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
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
        return None  # caller treats None as "unavailable" and FAILs that check


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def food_orders(db, where="", params=()):
    return db_query(db,
        "SELECT order_number, user_id, location_id, pickup_mode, pickup_date, "
        "pickup_time, contact_name, contact_phone, payment_method, "
        "gift_card_number, caniac_offer, subtotal, discount, tax, total, status "
        f"FROM food_orders {where}", params)


def food_order_items(db, order_number):
    return db_query(db,
        "SELECT mi.slug, mi.name, foi.quantity_label, foi.selections, foi.line_total "
        "FROM food_order_items foi JOIN food_orders fo ON fo.id=foi.order_id "
        "JOIN menu_items mi ON mi.id=foi.item_id "
        "WHERE fo.order_number=? ORDER BY foi.id", (order_number,))


def gear_orders(db, where="", params=()):
    return db_query(db,
        "SELECT order_number, user_id, email, ship_name, ship_line1, ship_city, "
        "ship_state, ship_zip, payment_method, subtotal, shipping, total "
        f"FROM gear_orders {where}", params)


def gear_order_items(db, order_number):
    return db_query(db,
        "SELECT gp.handle, gp.title, goi.variant_title, goi.qty, goi.price "
        "FROM gear_order_items goi JOIN gear_orders go ON go.id=goi.order_id "
        "JOIN gear_products gp ON gp.id=goi.product_id "
        "WHERE go.order_number=? ORDER BY goi.id", (order_number,))


def gift_card_balance(db, card_number):
    rows = db_query(db, "SELECT balance FROM gift_cards WHERE card_number=?",
                    (card_number,))
    return rows[0][0] if rows else None


def caniac_points(db, email):
    rows = db_query(db,
        "SELECT cc.points FROM caniac_cards cc JOIN users u ON u.id=cc.user_id "
        "WHERE u.email=?", (email,))
    return rows[0][0] if rows else None


def user_phone(db, email):
    rows = db_query(db, "SELECT phone FROM users WHERE email=?", (email,))
    return rows[0][0] if rows else None


def user_addresses(db, email):
    return db_query(db,
        "SELECT a.label, a.line1, a.city, a.state, a.zip_code FROM addresses a "
        "JOIN users u ON u.id=a.user_id WHERE u.email=? ORDER BY a.id", (email,))


def location_by_slug(db, slug):
    rows = db_query(db,
        "SELECT id, street, city, state, zip_code, phone, drive_thru_hours "
        "FROM locations WHERE slug=?", (slug,))
    return rows[0] if rows else None


def next_food_order_number(db):
    """Highest food order number currently in the DB (seed tops out at RC-100239)."""
    rows = db_query(db, "SELECT order_number FROM food_orders ORDER BY id DESC LIMIT 1")
    return rows[0][0] if rows else None


def new_food_orders(db, seed_tops="RC-100239"):
    """All food orders placed AFTER the seed set (id > seed max)."""
    return db_query(db,
        "SELECT order_number, user_id, location_id, pickup_mode, pickup_date, "
        "pickup_time, contact_name, contact_phone, payment_method, "
        "gift_card_number, caniac_offer, subtotal, discount, tax, total, status "
        "FROM food_orders WHERE order_number > ? ORDER BY id", (seed_tops,))


def new_gear_orders(db, seed_tops="GEAR-4503"):
    return db_query(db,
        "SELECT order_number, user_id, email, ship_name, ship_line1, ship_city, "
        "ship_state, ship_zip, payment_method, subtotal, shipping, total "
        "FROM gear_orders WHERE order_number > ? ORDER BY id", (seed_tops,))


# ---------------------------------------------------------------- judge harness


class Judge:
    def __init__(self, task_id):
        self.task_id = task_id
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

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence},
                         indent=2))
        sys.exit(0 if self.ok else 1)


def parse_args():
    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-rc-review")

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    argv = sys.argv[1:]
    args = VerifyArgs()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--run_dir":
            args.run_dir = argv[i + 1]; i += 2
        elif a == "--initial_db":
            args.initial_db = argv[i + 1]; i += 2
        elif a == "--after_db":
            args.after_db = argv[i + 1]; i += 2
        elif a == "--container":
            args.container = argv[i + 1]; i += 2
        else:
            raise SystemExit(f"unknown argument: {a}")
    if args.run_dir:
        run = Path(args.run_dir)
        if not args.initial_db and (run / "initial.db").is_file():
            args.initial_db = str(run / "initial.db")
        if not args.after_db and (run / "after.db").is_file():
            args.after_db = str(run / "after.db")
    args.post_process()
    return args
