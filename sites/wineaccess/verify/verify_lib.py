#!/usr/bin/env python3
"""Deterministic grading for the 18 WineAccess benchmark tasks."""

import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote


SITE = "wineaccess"
TASK_COUNT = 18
STATEFUL_TASKS = {0, 1, 4, 5, 7, 10, 13, 14, 16}


def _alt(*groups):
    return tuple(tuple(group) if isinstance(group, (tuple, list)) else (group,) for group in groups)


NAV_ALTERNATIVES = {
    0: (_alt("/login", "/store/", ("2021-bank-shot", "2023-1881-napa", "2023-karo-kann", "2023-off-the-cuff"), "/cart"),),
    1: (_alt("/login", ("/search", "/store/"), ("2023-glassmen", "2024-raen"), "/saved"),),
    2: (_alt("2022-dumol", "2022-fantesca"),),
    3: (_alt("/store/", "2015-chateau-haut-brion"),),
    4: (_alt("/login", "/store/sparkling", "m-brugnon", "/cart"),),
    5: (_alt("/login", "/account"),),
    6: (_alt("/login", "/orders"),),
    7: (_alt("/login", "/store/", "2023-domaine-roland", "/cart"),),
    8: (_alt("/store/", "2021-pas-de-cheval-cabernet-sauvignon-prelude-oakville"),),
    9: (_alt("2021-le-pich", "2021-bank-shot"),),
    10: (_alt("/login", "/club/", "/club/connoisseurs", "/account"),),
    11: (_alt("/contact-us"),),
    12: (_alt(("/search", "/store/"), "2017-maison-leroy-nuits", "2017-maison-leroy-gevrey", "2021-domaine-du-clos-de-tart"),),
    13: (_alt("/register", "/store/", ("/wine/", "/catalog/"), "/cart", "/checkout"),),
    14: (_alt("/login", "/cart"),),
    15: (_alt("/store/regions/italy", "2024-etna-bianco"),),
    16: (_alt("/login", "/cart", "/checkout", "/orders/"),),
    17: (_alt("/where-we-ship"),),
}


PASS_ANSWERS = {
    0: "Added a qualifying Napa Valley Cabernet Sauvignon under $50 to Alice's cart.",
    1: "Saved a qualifying Sonoma Coast Pinot Noir scoring at least 94 points.",
    2: "Fantesca Estate Chardonnay has the later drinking window, 2026-2037.",
    3: "2015 Chateau Haut-Brion Pessac-Leognan; Pessac-Leognan; $950.",
    4: "Added M. Brugnon Selection Brut Champagne; a suggested pairing is fried chicken.",
    5: "Updated Alice's favorite variety to Pinot Noir.",
    6: "The tracking number is 9400111899.",
    7: "Added 2 bottles of the 2023 Domaine Roland Lavantureux Chablis.",
    8: "The drinking window is 2026-2031.",
    9: "Bank Shot is lower at $39.60 per bottle; Le Pich is $57.20.",
    10: "Joined the Connoisseurs Club and confirmed it on Carol's account.",
    11: "WineAccess, Inc., 122 Camino Oruga, Building A, Napa, CA 94558; (866) 946-3923.",
    12: "Maison Leroy Gevrey-Chambertin has the later window, 2026-2035.",
    13: "Created an account, added a qualifying red blend, and reached checkout without ordering.",
    14: "Removed one cart item and confirmed the total changed.",
    15: "2024 Etna Bianco Carricante; pair with roast chicken, shellfish, or spring vegetables.",
    16: "Checkout completed; the new order number is reported from the order page.",
    17: "During heat or cold events, members can delay shipping to protect bottle condition.",
}


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _all(value, *tokens):
    folded = _norm(value)
    return all(_norm(token) in folded for token in tokens)


def _any(value, *tokens):
    folded = _norm(value)
    return any(_norm(token) in folded for token in tokens)


def _numbers(value):
    return [float(item) for item in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", str(value or "").replace(",", ""))]


def _number(value, expected, tolerance=0.01):
    return any(math.isclose(item, expected, rel_tol=0, abs_tol=tolerance) for item in _numbers(value))


def answer_ok(index, answer):
    if index in STATEFUL_TASKS and not answer.strip():
        return False
    if index == 0:
        return _all(answer, "cart")
    if index == 1:
        return _any(answer, "saved", "cellar")
    if index == 2:
        return _all(answer, "fantesca", "2026", "2037")
    if index == 3:
        return _all(answer, "haut-brion", "pessac-leognan") and _number(answer, 950)
    if index == 4:
        return _all(answer, "brugnon") and _any(answer, "fried chicken", "triple cream", "celebrations")
    if index == 5:
        return _all(answer, "pinot noir")
    if index == 6:
        return _all(answer, "9400111899")
    if index == 7:
        return _all(answer, "domaine roland", "chablis") and _number(answer, 2)
    if index == 8:
        return _all(answer, "2026", "2031")
    if index == 9:
        return _all(answer, "bank shot") and _number(answer, 39.60) and _number(answer, 57.20)
    if index == 10:
        return _all(answer, "connoisseurs")
    if index == 11:
        return _all(answer, "122 camino oruga", "building a", "napa", "94558") and _all(re.sub(r"\D", "", answer), "8669463923")
    if index == 12:
        return _all(answer, "gevrey-chambertin", "2026", "2035")
    if index == 13:
        return _all(answer, "checkout") and _any(answer, "without", "not placed", "did not place")
    if index == 14:
        return _all(answer, "removed") and _all(answer, "total")
    if index == 15:
        return _all(answer, "etna bianco") and _any(answer, "roast chicken", "shellfish", "spring vegetables")
    if index == 16:
        return bool(re.search(r"\bWA-\d{6}-\d+\b", answer, re.I)) or _all(answer, "order number")
    if index == 17:
        return _any(answer, "heat", "cold") and _any(answer, "delay", "hold") and _any(answer, "protect", "condition")
    return False


def load_run(run_dir):
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def step_urls(traj):
    return [unquote(str(step.get("url", ""))).casefold() for step in traj.get("steps", [])]


def navigation_ok(index, traj):
    urls = step_urls(traj)
    for alternative in NAV_ALTERNATIVES[index]:
        if all(any(any(needle.casefold() in url for needle in group) for url in urls) for group in alternative):
            return True
    return False


def _query(db_path, sql, params=()):
    if not db_path or not Path(db_path).exists():
        return []
    with sqlite3.connect(db_path) as connection:
        return connection.execute(sql, params).fetchall()


def _scalar(db_path, sql, params=()):
    rows = _query(db_path, sql, params)
    return rows[0][0] if rows else None


def _user_id(db_path, email):
    return _scalar(db_path, "SELECT id FROM users WHERE lower(email)=lower(?)", (email,))


def state_ok(index, initial_db, after_db, answer):
    if index not in STATEFUL_TASKS:
        return True, "not_stateful"
    if not initial_db or not after_db:
        return False, "database_evidence_missing"
    before_alice = _user_id(initial_db, "alice.j@test.com")
    after_alice = _user_id(after_db, "alice.j@test.com")
    if index == 0:
        rows = _query(after_db, "SELECT c.quantity FROM cart_items c JOIN wines w ON w.id=c.wine_id WHERE c.user_id=? AND w.variety='Cabernet Sauvignon' AND w.region='Napa Valley' AND w.price<50", (after_alice,))
        old = sum(row[0] for row in _query(initial_db, "SELECT c.quantity FROM cart_items c JOIN wines w ON w.id=c.wine_id WHERE c.user_id=? AND w.variety='Cabernet Sauvignon' AND w.region='Napa Valley' AND w.price<50", (before_alice,)))
        return sum(row[0] for row in rows) > old, "qualifying_cart_add"
    if index == 1:
        old = set(_query(initial_db, "SELECT wine_id FROM wishlist_items WHERE user_id=?", (before_alice,)))
        new = set(_query(after_db, "SELECT wi.wine_id FROM wishlist_items wi JOIN wines w ON w.id=wi.wine_id WHERE wi.user_id=? AND w.variety='Pinot Noir' AND w.region='Sonoma Coast' AND w.score>=94", (after_alice,)))
        return bool(new-old), "qualifying_saved_add"
    if index == 4:
        wine = _scalar(after_db, "SELECT id FROM wines WHERE slug='m-brugnon-selection-brut-champagne'")
        old = _scalar(initial_db, "SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=? AND wine_id=?", (before_alice, wine)) or 0
        new = _scalar(after_db, "SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=? AND wine_id=?", (after_alice, wine)) or 0
        return new > old, "less_expensive_champagne_added"
    if index == 5:
        old = _scalar(initial_db, "SELECT favorite_variety FROM users WHERE id=?", (before_alice,))
        new = _scalar(after_db, "SELECT favorite_variety FROM users WHERE id=?", (after_alice,))
        return new == "Pinot Noir" and old != new, "favorite_variety_updated"
    if index == 7:
        wine = _scalar(after_db, "SELECT id FROM wines WHERE slug='2023-domaine-roland-lavantureux-vieilles-vignes-chablis'")
        old = _scalar(initial_db, "SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=? AND wine_id=?", (before_alice, wine)) or 0
        new = _scalar(after_db, "SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=? AND wine_id=?", (after_alice, wine)) or 0
        return new-old >= 2, "two_french_white_bottles_added"
    if index == 10:
        before_carol = _user_id(initial_db, "carol.d@test.com")
        after_carol = _user_id(after_db, "carol.d@test.com")
        club = _scalar(after_db, "SELECT id FROM clubs WHERE slug='connoisseurs'")
        old = _scalar(initial_db, "SELECT COUNT(*) FROM club_memberships WHERE user_id=? AND club_id=?", (before_carol, club)) or 0
        new = _scalar(after_db, "SELECT COUNT(*) FROM club_memberships WHERE user_id=? AND club_id=?", (after_carol, club)) or 0
        return old == 0 and new == 1, "connoisseurs_membership_added"
    if index == 13:
        old_ids = {row[0] for row in _query(initial_db, "SELECT id FROM users")}
        new_ids = {row[0] for row in _query(after_db, "SELECT id FROM users")}-old_ids
        if len(new_ids) != 1:
            return False, "exactly_one_new_account"
        uid = next(iter(new_ids))
        qualifying = _scalar(after_db, "SELECT COUNT(*) FROM cart_items c JOIN wines w ON w.id=c.wine_id WHERE c.user_id=? AND w.variety LIKE '%Blend%' AND w.wine_type='Red' AND w.price<30", (uid,)) or 0
        orders = _scalar(after_db, "SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)) or 0
        return qualifying >= 1 and orders == 0, "new_account_red_blend_at_checkout"
    if index == 14:
        before_david = _user_id(initial_db, "david.k@test.com")
        after_david = _user_id(after_db, "david.k@test.com")
        old = _scalar(initial_db, "SELECT COALESCE(SUM(c.quantity*w.price),0) FROM cart_items c JOIN wines w ON w.id=c.wine_id WHERE c.user_id=?", (before_david,)) or 0
        new = _scalar(after_db, "SELECT COALESCE(SUM(c.quantity*w.price),0) FROM cart_items c JOIN wines w ON w.id=c.wine_id WHERE c.user_id=?", (after_david,)) or 0
        return new < old, "cart_total_decreased"
    if index == 16:
        old_orders = set(_query(initial_db, "SELECT order_number FROM orders WHERE user_id=?", (before_alice,)))
        new_orders = set(_query(after_db, "SELECT order_number FROM orders WHERE user_id=?", (after_alice,)))-old_orders
        cart_count = _scalar(after_db, "SELECT COUNT(*) FROM cart_items WHERE user_id=?", (after_alice,)) or 0
        answer_match = re.search(r"\bWA-\d{6}-\d+\b", answer, re.I)
        return len(new_orders) == 1 and cart_count == 0 and (not answer_match or (answer_match.group(0),) in new_orders), "new_order_and_empty_cart"
    return False, "unknown_stateful_task"


def evaluate(index, traj, initial_db=None, after_db=None):
    if not navigation_ok(index, traj):
        return {"pass": False, "reason": "required_navigation"}
    answer = str(traj.get("final_answer") or "").strip()
    if not answer_ok(index, answer):
        return {"pass": False, "reason": "frozen_answer"}
    state_pass, state_reason = state_ok(index, initial_db, after_db, answer)
    if not state_pass:
        return {"pass": False, "reason": state_reason}
    return {"pass": True, "reason": "verified"}


def _fetch_db(container, kind):
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, path], capture_output=True, text=True)
    if result.returncode:
        os.unlink(path)
        return None
    return path


def main(index):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=os.environ.get("WEBHARBOR_CONTAINER", "webharbor"))
    args = parser.parse_args()
    cleanup = []
    initial = args.initial_db
    after = args.after_db
    if index in STATEFUL_TASKS:
        if not initial:
            initial = _fetch_db(args.container, "instance_seed")
            if initial: cleanup.append(initial)
        if not after:
            after = _fetch_db(args.container, "instance")
            if after: cleanup.append(after)
    try:
        result = evaluate(index, load_run(args.run_dir), initial, after)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["pass"] else 1
    finally:
        for path in cleanup:
            try: os.unlink(path)
            except OSError: pass
