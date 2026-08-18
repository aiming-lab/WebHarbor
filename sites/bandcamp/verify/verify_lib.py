#!/usr/bin/env python3
"""Deterministic grading helpers for the Bandcamp benchmark tasks.

All tasks require a frozen answer and navigation to the page(s) exposing it.
Tasks 3, 4, 7, and 8 also compare seed and live SQLite databases so that a
plausible self-report cannot pass without the requested state transition.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


SITE = "bandcamp"
TASK_COUNT = 18
STATEFUL_TASKS = {3, 4, 7, 8}


def _alt(*groups):
    """One valid navigation alternative made from required URL groups."""
    return tuple(tuple(group) if isinstance(group, (list, tuple)) else (group,)
                 for group in groups)


NAV_ALTERNATIVES = {
    0: (_alt("/search", "q=neon", "/album/tidal-memory"),),
    1: (_alt("/discover", "scene=tokyo-japan", "genre=ambient",
             "/album/between-stations"),),
    2: (_alt("/artist/ashen-circuit",
             "/merch/ashen-circuit-grid-slipmat"),),
    3: (_alt("/login", "/album/machine-prayer"),),
    4: (_alt("/login", "/merch/soft-locale-drift-hoodie"),),
    5: (_alt("/compare/releases", "tidal-memory", "harbor-burn"),),
    6: (_alt("/album/tidal-memory"),),
    7: (_alt("/login", "/cart", "/checkout", "/orders/"),),
    8: (_alt("/login", "/account/edit"),),
    9: (_alt("/login", "/orders"),),
    10: (_alt("/discover", "scene=berlin-germany",
              "genre=experimental", "tag=microtone",
              "/album/resin-language"),),
    11: (_alt("/discover", "scene=london-united-kingdom", "genre=pop",
              "/album/elastic-hearts"),),
    12: (_alt("/artist/velvet-avenue",
              "/merch/velvet-avenue-night-shift-poster"),),
    13: (_alt("/album/blue-hour-broadcast"),),
    14: (_alt("/login", "/collection"),),
    15: (_alt("/search", "q=small-room", "/artist/glass-choir",
              "/album/static-bloom"),),
    16: (_alt("/discover", "scene=los-angeles-united-states", "genre=rock",
              "/album/harbor-burn"),),
    17: (_alt("/artist/salt-meadow",
              "/merch/salt-meadow-field-notes-tote"),),
}


PASS_ANSWERS = {
    0: "The cassette edition of Tidal Memory costs $15.00.",
    1: "The third track is Between Stations.",
    2: "The cheaper option is Pair at $22.00.",
    3: "Machine Prayer was added to Alice's wishlist.",
    4: "The Medium Soft Locale Drift Hoodie was added to Bob's cart.",
    5: "Tidal Memory is longer (20:10 versus Harbor Burn at 17:55).",
    6: "Track 4, Low Pier, lasts 4:31.",
    7: "Checkout completed as order BC-20260501-0006.",
    8: "David's preferred format is now Vinyl and his city is Eugene.",
    9: "Alice's most recent seeded order is BC-20260426-0002.",
    10: "Resin Language's Digital Album costs $8.50.",
    11: "Elastic Hearts offers CD and vinyl as physical formats.",
    12: "The signed Velvet Avenue Night Shift Poster costs $27.00.",
    13: "The cheapest format is Digital Album at $9.50.",
    14: "The favorite track is Between Stations.",
    15: "Glass Choir's newest album is Static Bloom.",
    16: "The closing track is Wide Exit.",
    17: "The two tote colors are Natural and Forest.",
}


EXPECTED = {
    0: "Tidal Memory cassette; $15.00",
    1: "third track: Between Stations",
    2: "Pair; $22.00",
    3: "Machine Prayer added to Alice's wishlist, plus matching DB state",
    4: "Medium hoodie added to Bob's cart, plus matching DB state",
    5: "Tidal Memory is longer (20:10 versus 17:55)",
    6: "track 4: Low Pier; 4:31",
    7: "checkout order BC-20260501-0006, plus matching DB state",
    8: "Vinyl and Eugene, plus matching DB state",
    9: "BC-20260426-0002",
    10: "Resin Language digital; $8.50",
    11: "CD and vinyl",
    12: "signed poster; $27.00",
    13: "Digital Album; $9.50",
    14: "Between Stations",
    15: "Static Bloom",
    16: "Wide Exit",
    17: "Natural and Forest",
}


def load_run(run_dir):
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def step_urls(traj):
    return [unquote(str(step.get("url", ""))).casefold()
            for step in traj.get("steps", [])]


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def _navigation_ok(task_index, traj):
    urls = step_urls(traj)
    for alternative in NAV_ALTERNATIVES[task_index]:
        if all(any(any(needle.casefold() in url for needle in group)
                   for url in urls) for group in alternative):
            return True, urls
    return False, urls


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _has_all(text, *tokens):
    value = _norm(text)
    return all(_norm(token) in value for token in tokens)


def _has_any(text, *tokens):
    value = _norm(text)
    return any(_norm(token) in value for token in tokens)


def _numbers(text):
    cleaned = (text or "").replace(",", "")
    return [float(value) for value in re.findall(
        r"(?<![\w.])[-+]?\d+(?:\.\d+)?", cleaned
    )]


def _has_number(text, expected, tolerance=0.005):
    return any(math.isclose(value, expected, abs_tol=tolerance, rel_tol=0)
               for value in _numbers(text))


def answer_ok(task_index, answer):
    if not answer.strip():
        return False
    if task_index == 0:
        return _has_all(answer, "cassette") and _has_number(answer, 15)
    if task_index == 1:
        return _has_all(answer, "between stations")
    if task_index == 2:
        return (_has_all(answer, "pair") and _has_number(answer, 22)
                and not _has_all(answer, "glow"))
    if task_index == 3:
        return (_has_all(answer, "machine prayer")
                and _has_any(answer, "wishlist", "wish list", "saved", "added"))
    if task_index == 4:
        return (_has_all(answer, "hoodie")
                and _has_any(answer, "medium", "size m")
                and _has_any(answer, "cart", "added"))
    if task_index == 5:
        return _has_all(answer, "tidal memory", "longer")
    if task_index == 6:
        return (_has_all(answer, "4:31") or _has_number(answer, 271))
    if task_index == 7:
        return (_has_any(answer, "checkout", "order", "completed")
                and _has_all(answer, "bc-20260501-0006"))
    if task_index == 8:
        return _has_all(answer, "vinyl", "eugene")
    if task_index == 9:
        return _has_all(answer, "bc-20260426-0002")
    if task_index == 10:
        return _has_all(answer, "digital") and _has_number(answer, 8.5)
    if task_index == 11:
        return (_has_all(answer, "cd", "vinyl")
                and not _has_all(answer, "digital"))
    if task_index == 12:
        return _has_all(answer, "signed") and _has_number(answer, 27)
    if task_index == 13:
        return _has_all(answer, "digital") and _has_number(answer, 9.5)
    if task_index == 14:
        return _has_all(answer, "between stations")
    if task_index == 15:
        return _has_all(answer, "static bloom")
    if task_index == 16:
        return _has_all(answer, "wide exit")
    if task_index == 17:
        return _has_all(answer, "natural", "forest")
    raise ValueError(f"unknown task index: {task_index}")


def _fetch_db(container, kind):
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    result = subprocess.run(
        ["docker", "cp", source, path], capture_output=True, text=True
    )
    if result.returncode:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    return path


def _resolve_db(path, container, kind):
    return path or _fetch_db(container, kind)


def _query(db_path, sql, params=()):
    if not db_path or not Path(db_path).exists():
        return None
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _wishlist_rows(db_path):
    return _query(
        db_path,
        "SELECT wi.id FROM wishlist_items wi "
        "JOIN users u ON u.id=wi.user_id "
        "JOIN albums a ON a.id=wi.album_id "
        "WHERE u.email=? AND a.slug=? ORDER BY wi.id",
        ("alice.j@test.com", "machine-prayer"),
    )


def _hoodie_cart_rows(db_path):
    return _query(
        db_path,
        "SELECT ci.id, fv.name, fv.option_a, fv.option_b, ci.quantity "
        "FROM cart_items ci JOIN users u ON u.id=ci.user_id "
        "JOIN merch_items m ON m.id=ci.merch_item_id "
        "JOIN format_variants fv ON fv.id=ci.format_variant_id "
        "WHERE u.email=? AND m.slug=? ORDER BY ci.id",
        ("bob.c@test.com", "soft-locale-drift-hoodie"),
    )


def _user_profile(db_path):
    rows = _query(
        db_path,
        "SELECT city, favorite_format FROM users WHERE email=?",
        ("david.k@test.com",),
    )
    return rows[0] if rows and len(rows) == 1 else None


def _bob_orders(db_path):
    return _query(
        db_path,
        "SELECT o.id, o.order_number, o.status, o.shipping_line1, "
        "o.shipping_city, o.shipping_country FROM orders o "
        "JOIN users u ON u.id=o.user_id WHERE u.email=? ORDER BY o.id",
        ("bob.c@test.com",),
    )


def _bob_cart(db_path):
    return _query(
        db_path,
        "SELECT COALESCE(a.title, m.title), fv.name, ci.quantity "
        "FROM cart_items ci JOIN users u ON u.id=ci.user_id "
        "LEFT JOIN albums a ON a.id=ci.album_id "
        "LEFT JOIN merch_items m ON m.id=ci.merch_item_id "
        "LEFT JOIN format_variants fv ON fv.id=ci.format_variant_id "
        "WHERE u.email=? ORDER BY ci.id",
        ("bob.c@test.com",),
    )


def _order_items(db_path, order_id):
    return _query(
        db_path,
        "SELECT title, variant_label, quantity FROM order_items "
        "WHERE order_id=? ORDER BY id",
        (order_id,),
    )


def _wishlist_state_ok(initial_db, after_db):
    before = _wishlist_rows(initial_db)
    after = _wishlist_rows(after_db)
    ok = before == [] and after is not None and len(after) == 1
    return ok, f"initial={before!r}; after={after!r}"


def _hoodie_state_ok(initial_db, after_db):
    before = _hoodie_cart_rows(initial_db)
    after = _hoodie_cart_rows(after_db)
    exact = (
        before == [] and after is not None and len(after) == 1
        and str(after[0][2]).casefold() == "m"
        and int(after[0][4]) >= 1
    )
    return exact, f"initial={before!r}; after={after!r}"


def _checkout_state_ok(initial_db, after_db):
    before_orders = _bob_orders(initial_db)
    after_orders = _bob_orders(after_db)
    before_cart = _bob_cart(initial_db)
    after_cart = _bob_cart(after_db)
    if None in (before_orders, after_orders, before_cart, after_cart):
        return False, (f"orders={before_orders!r}->{after_orders!r}; "
                       f"cart={before_cart!r}->{after_cart!r}")
    expected_cart = {"Signal Debt", "Cinder Plaza Blueprint Fever Poster"}
    initial_titles = {row[0] for row in before_cart}
    initial_ids = {row[0] for row in before_orders}
    created = [row for row in after_orders if row[0] not in initial_ids]
    items = _order_items(after_db, created[0][0]) if len(created) == 1 else None
    item_titles = {row[0] for row in items} if items is not None else set()
    order_exact = False
    if len(created) == 1:
        _, number, status, line1, city, country = created[0]
        order_exact = (
            number == "BC-20260501-0006" and status == "paid"
            and line1 == "77 Fulton Market" and city == "Chicago"
            and country == "United States"
        )
    ok = (
        initial_titles == expected_cart and after_cart == []
        and len(created) == 1 and order_exact and item_titles == expected_cart
        and all(int(row[2]) >= 1 for row in (items or []))
    )
    return ok, (f"orders={before_orders!r}->{after_orders!r}; "
                f"cart={before_cart!r}->{after_cart!r}; items={items!r}")


def _profile_state_ok(initial_db, after_db):
    before = _user_profile(initial_db)
    after = _user_profile(after_db)
    ok = before == ("Portland", "shirt") and after == ("Eugene", "vinyl")
    return ok, f"initial={before!r}; after={after!r}"


STATE_CHECKS = {
    3: ("wishlist_after_state", _wishlist_state_ok),
    4: ("cart_after_state", _hoodie_state_ok),
    7: ("checkout_after_state", _checkout_state_ok),
    8: ("profile_after_state", _profile_state_ok),
}


def evaluate(task_index, traj, initial_db="", after_db="", container="wh-review"):
    if task_index not in NAV_ALTERNATIVES:
        raise ValueError(f"unknown task index: {task_index}")
    answer = final_answer(traj)
    nav_ok, urls = _navigation_ok(task_index, traj)
    checks = [
        ("final_answer_nonempty", bool(answer), f"final={answer!r}"),
        ("required_navigation", nav_ok, f"urls={urls!r}"),
        ("frozen_answer", answer_ok(task_index, answer),
         f"expected={EXPECTED[task_index]}; final={answer!r}"),
    ]
    if task_index in STATEFUL_TASKS:
        initial_db = _resolve_db(initial_db, container, "instance_seed")
        after_db = _resolve_db(after_db, container, "instance")
        name, state_check = STATE_CHECKS[task_index]
        ok, detail = state_check(initial_db, after_db)
        checks.append((name, ok, detail))

    passed = all(ok for _, ok, _ in checks)
    reason = next((name for name, ok, _ in checks if not ok), "")
    evidence = [f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
                for name, ok, detail in checks]
    return {
        "task_id": f"Bandcamp--{task_index}",
        "pass": passed,
        "reason": reason,
        "evidence": evidence,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument(
        "--container", default=os.environ.get("WH_CONTAINER", "wh-review")
    )
    parser.add_argument("--no_llm", nargs="?", const="True", default="False")
    return parser.parse_args()


def main(task_index):
    args = parse_args()
    verdict = evaluate(
        task_index,
        load_run(args.run_dir),
        initial_db=args.initial_db,
        after_db=args.after_db,
        container=args.container,
    )
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["pass"] else 1)
