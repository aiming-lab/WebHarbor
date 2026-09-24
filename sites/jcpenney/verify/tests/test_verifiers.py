"""Deterministic verifier contract tests for the 15 redesigned JCPenney tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a clean
seed pair; stateful tasks against the seed with the exact allowed sqlite delta);
a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a wrong answer MUST
FAIL; a shortcut (correct answer, homepage-only navigation) MUST FAIL — every
task's required surface is beyond the homepage. Read-only tasks MUST FAIL on a
mutated after-DB; stateful tasks MUST FAIL on a state-mismatch (no DB delta) and
on a wrong delta (wrong amounts / wrong rows / wrong user / wrong hash / wrong
gift message / wrong quantity). Package tampering (task_id mismatch, off-site
URLs, missing screenshots, non-done trajectory, tampered seed, unavailable DB)
MUST fail closed. Parallel-answer attribution swaps (two stores, three category
claims) are adversarial wrong-answer cases.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, SEED_DB, _acquire_seed, build_run,  # noqa: E402
                      copy_db, mutate_db, noop_run, run_verifier)

pytestmark = pytest.mark.skipif(False, reason="seed DB unavailable")

# KEEP 0/1/2 (register cycle / address add / password cycle) + redesigned
# purchase chains 3/4/5/7/8/10/14 are stateful; the dual-view order check, the
# two-store comparison and the three read/analysis chains are read-only.
STATEFUL = {0, 1, 2, 3, 4, 5, 7, 8, 10, 14}
READ_ONLY = sorted(set(range(15)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}

HOPE = "/p/st-john-s-bay-womens-hope-stacked-heel-booties/ppr5008660553"
KINNEL = "/p/st-john-s-bay-womens-kinnel-flat-heel-booties/ppr5008660563"
MAXBLACKOUT = "/p/max-blackout-mystique-grommet-top-100-blackout-single-curtain-panel/ppr5007989193"
SHEET1000 = "/p/liz-claiborne-luxury-performance-1000tc-sheet-set/ppr5008236237"
BIOLAGE = "/p/biolage-color-last-shampoo-33-8-oz/pp5004960667"
PAPELL = "/p/papell-boutique-womens-v-neck-short-sleeve-cap-evening-gown/ppr5008618161"
MOCKNECK = "/p/st-john-s-bay-womens-mock-neck-long-sleeve-t-shirt/ppr5008659536"
CREATED = "2026-09-23 00:00:00.000000"
HASH = "jcpenney-webharbor-demo:"
GIFT_MESSAGE = "Congratulations on your graduation! Love, Aunt June"


def pw_hash(raw: str) -> str:
    import hashlib
    return hashlib.sha256(f"{HASH}{raw}".encode()).hexdigest()


# ---------------------------------------------------------------- navigation fixtures
def honest_steps(index: int):
    """[(path, action, params)] navigation for the honest run of task `index`."""
    def login(who, pw=PASSWORD):
        return [("/signin", "fill", {"text": LOGIN[who], "selector": "input[name=email]"}),
                ("/signin", "fill", {"text": pw, "selector": "input[name=password]"}),
                ("/signin", "click", {"selector": "button[type=submit]"},)]
    checkout = [("/checkout/shipping", "goto", {}),
                ("/checkout/payment", "goto", {}),
                ("/checkout/review", "goto", {})]
    S = {
        0: [("/register", "fill", {"text": "Honest", "selector": "input[name=first_name]"}),
            ("/register", "fill", {"text": "Runner", "selector": "input[name=last_name]"}),
            ("/register", "fill", {"text": "honest.t19runner@example.com", "selector": "input[name=email]"}),
            ("/register", "fill", {"text": "Shopper123!", "selector": "input[name=password]"}),
            ("/register", "fill", {"text": "Shopper123!", "selector": "input[name=confirm_password]"}),
            ("/register", "click", {"selector": "button[type=submit]"},),
            ("/account/dashboard", "goto", {}),
            ("/signin", "goto", {}),
            ("/signin", "fill", {"text": "honest.t19runner@example.com", "selector": "input[name=email]"}),
            ("/signin", "fill", {"text": "Shopper123!", "selector": "input[name=password]"}),
            ("/signin", "click", {"selector": "button[type=submit]"},)],
        1: login("alice") + [("/account/dashboard/profile", "goto", {})],
        2: login("carol") + [("/account/dashboard/profile", "goto", {}),
                            ("/signin", "fill", {"text": LOGIN["carol"], "selector": "input[name=email]"}),
                            ("/signin", "fill", {"text": "AutumnWalk45!", "selector": "input[name=password]"}),
                            ("/signin", "click", {"selector": "button[type=submit]"},)],
        3: [("/s/boots?sortBy=price_low", "goto", {}), (HOPE, "goto", {}), ("/cart", "goto", {})]
           + login("alice") + checkout
           + [("/checkout/confirmation/JCP123456001", "goto", {})],
        4: [("/register", "fill", {"text": "Pat", "selector": "input[name=first_name]"}),
            ("/register", "fill", {"text": "Quinn", "selector": "input[name=last_name]"}),
            ("/register", "fill", {"text": "pat.quinn@example.com", "selector": "input[name=email]"}),
            ("/register", "fill", {"text": "Shopper123!", "selector": "input[name=password]"}),
            ("/register", "fill", {"text": "Shopper123!", "selector": "input[name=confirm_password]"}),
            ("/register", "click", {"selector": "button[type=submit]"},),
            ("/s/blackout%20curtain%20panel?sortBy=price_high", "goto", {}),
            (MAXBLACKOUT, "goto", {}), ("/cart", "goto", {})]
           + checkout + [("/checkout/confirmation/JCP123456005", "goto", {})],
        5: login("carol") + [("/account/dashboard/wishlist", "goto", {}),
                             (BIOLAGE, "goto", {}), ("/cart", "goto", {})]
           + checkout + [("/checkout/confirmation/JCP123456003", "goto", {})],
        6: login("bob") + [("/account/dashboard/orders", "goto", {}),
                           ("/orders/JCP2609131004", "goto", {}),
                           ("/orders", "fill", {"text": "JCP2609131004", "selector": "input[name=order_number]"}),
                           ("/orders", "fill", {"text": "94110", "selector": "input[name=zip]"}),
                           ("/orders", "click", {"selector": "button[type=submit]"},)],
        7: [("/m/jcpenney-coupons", "goto", {}),
            ("/g/home-store/all-bedding?brand=liz+claiborne", "goto", {}),
            (SHEET1000, "goto", {}), ("/cart", "goto", {})]
           + login("carol") + checkout
           + [("/checkout/confirmation/JCP123456003", "goto", {})],
        8: login("bob") + [("/account/dashboard/profile", "goto", {}),
                           ("/account/dashboard/profile", "fill",
                            {"text": "4111111111111155", "selector": "input[name=card_number]"}),
                           ("/account/dashboard/profile", "fill",
                            {"text": "8", "selector": "input[name=exp_month]"}),
                           ("/account/dashboard/profile", "fill",
                            {"text": "2029", "selector": "input[name=exp_year]"}),
                           ("/account/dashboard/profile", "fill",
                            {"text": "Bob Chen", "selector": "input[name=cardholder]"}),
                           ("/account/dashboard/profile", "click",
                            {"selector": "button:has-text('Save Card')"},),
                           ("/cart", "goto", {})]
           + checkout + [("/checkout/confirmation/JCP123456002", "goto", {})],
        9: [("/stores?service=Curbside+Pick+up&state=WA", "goto", {}),
            ("/stores/2011", "goto", {}), ("/stores/2327", "goto", {})],
        10: [("/gift-cards", "fill",
              {"text": "6249881234570021", "selector": "input[name=card_number]"}),
             ("/gift-cards", "click", {"selector": "button:has-text('Check Balance')"},),
             ("/gift-cards", "click", {"selector": "button:has-text('Check Balance')"},)]
            + login("david") + [("/account/dashboard/wishlist", "goto", {}),
                                (PAPELL, "goto", {}), ("/cart", "goto", {})]
            + checkout + [("/checkout/confirmation/JCP123456004", "goto", {})],
        11: [("/g/shoes/all-womens-shoes?sortBy=price_low", "goto", {}),
             ("/g/women/tops?sortBy=price_low", "goto", {}),
             ("/g/women/shorts?sortBy=price_low", "goto", {})],
        12: [("/g/shoes/all-womens-shoes?sortBy=price_low", "goto", {}),
             ("/g/shoes/all-womens-shoes?sortBy=price_high", "goto", {}),
             ("/g/shoes/all-womens-shoes?sortBy=rating", "goto", {}),
             (HOPE, "goto", {})],
        13: login("david") + [("/account/dashboard/orders", "goto", {}),
                              ("/orders/JCP2609203008", "goto", {}),
                              ("/account/dashboard/wishlist", "goto", {}),
                              (PAPELL, "goto", {}),
                              ("/account/dashboard/rewards", "goto", {})],
        14: login("alice") + [("/cart", "goto", {}),
                              ("/cart/update/1", "select", {"value": "3", "selector": "select[name=quantity]"}),
                              ("/cart/remove/2", "click", {"selector": "button:has-text('Remove')"},),
                              ("/s/mock%20neck", "goto", {}),
                              (MOCKNECK, "goto", {}), ("/cart", "goto", {})]
           + checkout + [("/checkout/confirmation/JCP123456001", "goto", {})],
    }
    return S[index]


# ---------------------------------------------------------------- stateful mutations
def order_insert(order_id: int, order_number: str, user_id: int, email: str, sub: float,
                 disc: float, ship: float, tax: float, total: float, coupon: str,
                 ship_name: str, ship_addr: str, ship_city: str, ship_state: str,
                 ship_zip: str, ship_phone: str, pay_type: str, last4: str,
                 gift: str = "") -> tuple[str, tuple]:
    sql = ("INSERT INTO orders (id, order_number, user_id, email, status, placed_at, "
           "delivered_at, subtotal, discount, shipping, tax, total, coupon_code, ship_name, "
           "ship_address, ship_city, ship_state, ship_zip, ship_phone, payment_type, "
           "payment_last4, tracking_number, carrier, pickup_store, gift_message, created_at) "
           f"VALUES ({order_id}, '{order_number}', {user_id}, '{email}', 'Processing', "
           "'2026-09-23 12:34:56', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', NULL, ?, ?)")
    return (sql, (sub, disc, ship, tax, total, coupon, ship_name, ship_addr, ship_city,
                  ship_state, ship_zip, ship_phone, pay_type, last4, gift, CREATED))


def item_insert(item_id: int, order_id: int, product_id: int, name: str, brand: str,
                color: str, size: str, qty: int, price: float) -> tuple[str, tuple]:
    sql = ("INSERT INTO order_items (id, order_id, product_id, product_name, brand, color, "
           "size, quantity, unit_price, image_file, created_at) "
           f"VALUES ({item_id}, {order_id}, {product_id}, ?, ?, ?, ?, {qty}, ?, 'p.jpg', ?)")
    return (sql, (name, brand, color, size, price, CREATED))


def stateful_statements(index: int, variant: str = "ok"):
    """[(sql, params)] turning a seed copy into the honest after-state (or a wrong one)."""
    if index == 0:
        pwhash = pw_hash("WrongPass1!") if variant == "wrong_hash" else pw_hash("Shopper123!")
        return [("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
                 "rewards_member, rewards_points, rewards_tier, created_at) VALUES (5, "
                 "'honest.t19runner@example.com', ?, 'Honest', 'Runner', '', 0, 0, '', ?)",
                 (pwhash, CREATED))]
    if index == 1:
        uid = 2 if variant == "wrong_user" else 1
        return [("INSERT INTO addresses (id, user_id, label, first_name, last_name, line1, line2, "
                 "city, state, zip, phone, is_default, created_at) VALUES (7, ?, 'Brother', 'Alex', "
                 "'Johnson', '582 Rainier Ave S', '', 'Seattle', 'WA', '98144', "
                 "'(206) 555-0147', 0, ?)", (uid, CREATED))]
    if index == 2:
        pwhash = pw_hash("WrongPass1!") if variant == "wrong_hash" else pw_hash("AutumnWalk45!")
        return [("UPDATE users SET password_hash = ? WHERE email = 'carol.d@test.com'", (pwhash,))]
    if index == 3:
        # honest: subtotal 96.98 (Hope booties 27.99 + alice's flannel 31.49 + PUMA 37.50),
        # SAVE30 30% = 29.09, free shipping (subtotal >= 75), tax on discounted 5.60 -> 73.49
        if variant == "wrong_amounts":
            disc, tax, total = 20.70, 6.20, 79.99
        else:
            disc, tax, total = 29.09, 5.60, 73.49
        return [order_insert(9, "JCP123456001", 1, "alice.j@test.com", 96.98, disc, 0.0, tax,
                             total, "SAVE30", "Alice Johnson", "1460 Alderwood Mall Blvd",
                             "Lynnwood", "WA", "98037", "(206) 555-0147", "Visa", "4242"),
                item_insert(15, 9, 61, "Arizona Mens Hooded Long Sleeve Classic Fit Big and Tall "
                            "Twofer Flannel Shirt", "Arizona Jean Co", "Sidney Plaid", "2x-large",
                            1, 31.49),
                item_insert(16, 9, 53, "PUMA Sweatpants Mens Straight Mid Rise Regular Fit Fleece "
                            "Active Jogger Pant", "Puma", "Mouse Gray", "small", 1, 37.50),
                item_insert(17, 9, 105, "St. John's Bay Womens Hope Stacked Heel Booties",
                            "ST. JOHN'S BAY", "Cognac", "8", 1, 27.99),
                ("DELETE FROM cart_items WHERE user_id = 1", ())]
    if index == 4:
        if variant == "wrong_hash":
            user_sql = ("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
                        "rewards_member, rewards_points, rewards_tier, created_at) VALUES (5, "
                        "'pat.quinn@example.com', ?, 'Pat', 'Quinn', '', 0, 0, '', ?)",
                        (pw_hash("WrongPass1!"), CREATED))
        else:
            user_sql = ("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
                        "rewards_member, rewards_points, rewards_tier, created_at) VALUES (5, "
                        "'pat.quinn@example.com', ?, 'Pat', 'Quinn', '', 0, 0, '', ?)",
                        (pw_hash("Shopper123!"), CREATED))
        if variant == "wrong_amounts":
            disc, tax, total = 13.13, 3.25, 51.59
        else:
            disc, tax, total = 13.12, 3.25, 51.58
        return [user_sql,
                order_insert(9, "JCP123456005", 5, "pat.quinn@example.com", 52.50, disc, 8.95,
                             tax, total, "AUTUMN", "Pat Quinn", "412 Cedar St", "Denver", "CO",
                             "80203", "(303) 555-0184", "Visa", "1111"),
                item_insert(15, 9, 92, "Max Blackout Mystique Grommet Top 100% Blackout Single "
                            "Curtain Panel", "MAX BLACKOUT", "Sandstone", "", 1, 52.50)]
    if index == 5:
        if variant == "wrong_amounts":
            disc, tax, total = 37.02, 7.13, 93.51
        else:
            disc, tax, total = 37.02, 7.13, 93.50
        removed = 34 if variant == "wrong_row" else 8
        return [order_insert(9, "JCP123456003", 3, "carol.d@test.com", 123.39, disc, 0.0, tax,
                             total, "SAVE30", "Carol Davis", "515 N State St", "Chicago", "IL",
                             "60654", "(312) 555-0126", "American Express", "1005"),
                item_insert(15, 9, 3, "Maya Brooke Womens Embellished Jacket Dress",
                            "MAYA BROOKE", "Wine", "medium", 1, 78.39),
                item_insert(16, 9, 129, "Biolage Color Last Shampoo 33.8 oz.", "Biolage",
                            "One Color", "", 1, 45.00),
                ("DELETE FROM cart_items WHERE user_id = 3", ()),
                (f"DELETE FROM wishlist_items WHERE user_id = 3 AND product_id = {removed}", ())]
    if index == 7:
        if variant == "wrong_amounts":  # the "$10 flat off" misreading
            disc, tax, total = 10.00, 12.57, 149.94
        else:
            disc, tax, total = 24.36, 11.39, 149.40
        return [order_insert(9, "JCP123456003", 3, "carol.d@test.com", 162.37, disc, 0.0, tax,
                             total, "GOSHOP15", "Carol Davis", "515 N State St", "Chicago", "IL",
                             "60654", "(312) 555-0126", "American Express", "1005"),
                item_insert(15, 9, 3, "Maya Brooke Womens Embellished Jacket Dress",
                            "MAYA BROOKE", "Wine", "medium", 1, 78.39),
                item_insert(16, 9, 74, "Liz Claiborne Luxury Performance 1000tc Sheet Set",
                            "LIZ CLAIBORNE", "White", "", 2, 41.99),
                ("DELETE FROM cart_items WHERE user_id = 3", ())]
    if index == 8:
        last4 = "9999" if variant == "wrong_card" else "1155"
        flip = ("UPDATE payment_methods SET is_default = 0 WHERE user_id = 2 AND id = 3", ())
        return [("INSERT INTO payment_methods (id, user_id, card_type, last4, cardholder, "
                 "exp_month, exp_year, is_default, created_at) VALUES (6, 2, 'Visa', ?, "
                 "'Bob Chen', 8, 2029, 1, ?)", (last4, CREATED)),
                flip,
                order_insert(9, "JCP123456002", 2, "bob.c@test.com", 129.38, 0.0, 0.0, 10.67,
                             140.05, "", "Bob Chen", "2401 Mission St", "San Francisco", "CA",
                             "94110", "(415) 555-0183", "Visa", "1155"),
                item_insert(15, 9, 131, "Tree Hut Tropic Glow Getaway Mini Best Sellers Kit",
                            "Tree Hut", "Tropic Glow", "", 1, 23.99),
                item_insert(16, 9, 54, "PUMA Mens Straight Regular Fit Active Cargo Pant",
                            "Puma", "Black", "medium", 2, 45.00),
                item_insert(17, 9, 45, "St. John's Bay Premium Stretch Mens Classic Fit Long "
                            "Sleeve Shirt", "ST. JOHN'S BAY", "Blue", "large", 1, 15.39),
                ("DELETE FROM cart_items WHERE user_id = 2", ())]
    if index == 10:
        gift = "Happy birthday!" if variant == "wrong_gift" else GIFT_MESSAGE
        if variant == "wrong_amounts":
            tax, total = 13.75, 180.31
        else:
            tax, total = 13.74, 180.30
        return [order_insert(9, "JCP123456004", 4, "david.k@test.com", 166.56, 0.0, 0.0, tax,
                             total, "", "David Kim", "77 E Nationwide Blvd", "Columbus", "OH",
                             "43215", "(614) 555-0198", "Visa", "0679", gift),
                item_insert(15, 9, 86, "Threadmade Harvest Sentiment 4-pc. Napkins", "Threadmade",
                            "Natural", "", 2, 25.19),
                item_insert(16, 9, 25, "St. John's Bay Womens Long Sleeve Open Front Plus Cable "
                            "Knit Cardigan", "ST. JOHN'S BAY", "Oatmeal", "1x", 1, 26.59),
                item_insert(17, 9, 1, "Papell Boutique Womens V Neck Short Sleeve Cap Evening "
                            "Gown", "PAPELL BOUTIQUE", "Moonscape", "10", 1, 89.59),
                ("DELETE FROM cart_items WHERE user_id = 4", ())]
    if index == 14:
        if variant == "wrong_qty":
            flannel_qty, sub, tax, total = 2, 75.87, 6.26, 82.13
        else:
            flannel_qty, sub, tax, total = 3, 106.36, 8.77, 115.13
        return [order_insert(9, "JCP123456001", 1, "alice.j@test.com", sub, 0.0, 0.0, tax, total,
                             "", "Alice Johnson", "1460 Alderwood Mall Blvd", "Lynnwood", "WA",
                             "98037", "(206) 555-0147", "Visa", "4242"),
                item_insert(15, 9, 61, "Arizona Mens Hooded Long Sleeve Classic Fit Big and Tall "
                            "Twofer Flannel Shirt", "Arizona Jean Co", "Sidney Plaid", "2x-large",
                            flannel_qty, 31.49),
                item_insert(16, 9, 11, "St. John's Bay Womens Mock Neck Long Sleeve T-Shirt",
                            "ST. JOHN'S BAY", "Black", "medium", 1, 11.89),
                ("DELETE FROM cart_items WHERE user_id = 1", ())]
    raise ValueError(index)


# ---------------------------------------------------------------- honest answers (from the live DOM)
HONEST_ANSWERS = json.loads(Path(__file__).with_name("honest_answers.json").read_text())


def make_honest(tmp: Path, index: int, db_pair="clean"):
    """Build an honest run dir. db_pair: 'clean' (seed/seed) or 'stateful' (seed/mutated)."""
    seed = _acquire_seed()
    run = build_run(tmp, f"honest_{index:02d}", f"JCPenney--{index}")
    copy_db(seed, run.root / "initial.db")
    if index in STATEFUL and db_pair == "stateful":
        mutate_db(seed, run.root / "after.db", stateful_statements(index))
    else:
        copy_db(seed, run.root / "after.db")
    for path, action, params in honest_steps(index):
        run.step(path, action, params)
    run.done(HONEST_ANSWERS[str(index)])
    return run.root


@pytest.fixture(scope="session")
def seed():
    return _acquire_seed()


# ---------------------------------------------------------------- parametrized tests
@pytest.mark.parametrize("index", range(15))
def test_honest_passes(tmp_path, index):
    run_dir = make_honest(tmp_path, index, db_pair="stateful" if index in STATEFUL else "clean")
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is True, f"honest run failed: {json.dumps(verdict)[:900]}"


@pytest.mark.parametrize("index", range(15))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "no-op run must fail"
    assert verdict.get("reason"), "no-op failure must carry a reason"


@pytest.mark.parametrize("index", range(15))
def test_wrong_answer_fails(tmp_path, index):
    run_dir = make_honest(tmp_path, index, db_pair="stateful" if index in STATEFUL else "clean")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    wrong = {
        0: "I registered honest.t19runner@example.com and after signing back in the dashboard "
           "shows 'Hello, Someone Else'.",
        1: "The profile now lists 5 addresses and the new one is the default.",
        2: "The old password still works and the new one is rejected; nothing changed.",
        3: "The cheapest boots were the Pop Kayley slouch boots at $19.99; the new order number "
           "is ORDER-999, the discount is $20.00 and the total is $99.99.",
        4: "I bought the Linden Street Gwen Leaf panel at $66.50 with the code WATCH20; order "
           "JCP999999005, discount $10.00, total $60.00.",
        5: "7 items remain on the wish list; the new order JCP999999003 totals $80.00.",
        6: "Order JCP2609131004 is Cancelled, shipped via FedEx with tracking 999999, and "
           "contains a Levi's jacket at $88.00; the guest view shows a completely different "
           "shipment.",
        7: "GOSHOP15 applied the advertised flat $10 off exactly — the applied discount matches "
           "the coupon's advertised terms; the new order JCP999999003 totals $160.00.",
        8: "The order shows the Mastercard ending 5309; the profile lists 4 cards afterwards and "
           "the order total is $91.34.",
        9: "Alderwood Mall: Sunday 12:00-18:00, phone (360) 734-7412, Curbside Pick up. Bellis "
           "Fair Mall: Sunday 11:00-19:00, phone (425) 771-9555, Curbside Pick up. They differ.",
        10: "The gift card balance is $84.50 and it doubles on the second check; the new order "
            "JCP999999004 totals $153.03 and the confirmation echoed no gift message.",
        11: "Women's shoes cheapest is the Hope Stacked Heel Booties at $27.99 — the From "
            "$31.50 claim holds. Tees cheapest is the A.N.A Crew Neck Long Sleeve T-Shirt at "
            "$9.09 — the From $7.89 claim holds. Shorts cheapest is the A.N.A Chino Short at "
            "$8.99 — the From $12.99 claim holds.",
        12: "The cheapest shoe is the Inca Suede Loafer at $38.49; the most expensive is the "
            "Hope booties at $65.00; best rated is the Inca at 3.8 with 8 reviews; its breakdown "
            "shows 5 stars: 8 and 1 star: 2.",
        13: "Order JCP2609203009 is Delivered with total $99.99; the dress costs $50.00; the "
            "gown shows $250.00 - $400.00; rewards balance 1,204 points, tier Rewards Access, "
            "latest activity a Welcome bonus of 500 points on December 3, 2026.",
        14: "Right before placing the order the bag held the flannel at qty 2 ($62.98) plus "
            "boots at $27.99, subtotal $90.97; the final order total is $120.00.",
    }[index]
    traj["final_answer"] = wrong
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "wrong answer must fail"


@pytest.mark.parametrize("index", range(15))
def test_shortcut_fails(tmp_path, index):
    """Correct answer, homepage-only navigation = memory-recall shortcut, must FAIL."""
    seed = _acquire_seed()
    run = build_run(tmp_path, f"shortcut_{index:02d}", f"JCPenney--{index}")
    copy_db(seed, run.root / "initial.db")
    copy_db(seed, run.root / "after.db")
    run.step("/", "goto", {})
    run.done(HONEST_ANSWERS[str(index)], final_path="/")
    verdict = run_verifier(index, run.root)
    assert verdict.get("pass") is False, "homepage-only shortcut must fail"
    assert "final_answer_nonempty" != verdict.get("reason"), "must fail on navigation, not the answer"


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_mutation_fails(tmp_path, seed, index):
    run_dir = make_honest(tmp_path, index)
    stmt = {
        6: ("UPDATE orders SET status = 'Cancelled' WHERE order_number = 'JCP2609131004'", ()),
        9: ("UPDATE stores SET phone = '555-0000' WHERE number = 2011", ()),
        11: ("UPDATE products SET price = price + 1 WHERE id = 105", ()),
        12: ("UPDATE reviews SET rating = 1 WHERE id = 1", ()),
        13: ("UPDATE orders SET total = 99.99 WHERE order_number = 'JCP2609203008'", ()),
    }.get(index, ("UPDATE products SET price = price + 1 WHERE id = 1", ()))
    con = sqlite3.connect(str(run_dir / "after.db"))
    try:
        con.execute(*stmt)
        con.commit()
    finally:
        con.close()
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "mutated after-DB must fail the read-only check"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_stateful_no_delta_fails(tmp_path, seed, index):
    """Self-reported success but the DB is untouched = state mismatch, must FAIL."""
    run_dir = make_honest(tmp_path, index, db_pair="clean")  # after == seed
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "state mismatch (no DB delta) must fail"


@pytest.mark.parametrize("index,variant", [
    (0, "wrong_hash"), (1, "wrong_user"), (2, "wrong_hash"), (3, "wrong_amounts"),
    (4, "wrong_amounts"), (4, "wrong_hash"), (5, "wrong_row"), (7, "wrong_amounts"),
    (8, "wrong_card"), (10, "wrong_gift"), (14, "wrong_qty"),
])
def test_stateful_wrong_delta_fails(tmp_path, seed, index, variant):
    run = build_run(tmp_path, f"wrongdelta_{index:02d}_{variant}", f"JCPenney--{index}")
    copy_db(seed, run.root / "initial.db")
    mutate_db(seed, run.root / "after.db", stateful_statements(index, variant))
    for path, action, params in honest_steps(index):
        run.step(path, action, params)
    run.done(HONEST_ANSWERS[str(index)])
    verdict = run_verifier(index, run.root)
    assert verdict.get("pass") is False, f"wrong delta ({variant}) must fail"


# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fails(tmp_path):
    run_dir = make_honest(tmp_path, 12)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "JCPenney--13"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(12, run_dir)
    assert verdict.get("pass") is False


def test_offsite_urls_fail(tmp_path):
    run = build_run(tmp_path, "offsite", "JCPenney--12")
    copy_db(_acquire_seed(), run.root / "initial.db")
    copy_db(_acquire_seed(), run.root / "after.db")
    run.step("https://example.com/product", "goto", {}, url="https://example.com/product")
    run.step(HOPE, "goto", {})
    run.done("Cheapest: Hope Stacked Heel Booties $27.99; most expensive: Thane Block Heel "
             "Riding Boots $48.99; best rated: Hope booties 5.0 with 2 reviews; most reviewed: "
             "Inca Suede Loafers 3.8 with 8 reviews; breakdown 5 stars: 2, 1 star: 0.")
    verdict = run_verifier(12, run.root)
    assert verdict.get("pass") is False, "off-site URL must break the local-origin gate"


def test_missing_screenshot_fails(tmp_path):
    run_dir = make_honest(tmp_path, 12)
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(12, run_dir)
    assert verdict.get("pass") is False


def test_terminated_false_fails(tmp_path):
    run_dir = make_honest(tmp_path, 12)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(12, run_dir)
    assert verdict.get("pass") is False


def test_empty_steps_fail(tmp_path):
    run = build_run(tmp_path, "nosteps", "JCPenney--12")
    copy_db(_acquire_seed(), run.root / "initial.db")
    copy_db(_acquire_seed(), run.root / "after.db")
    run.steps = []
    run.done("Cheapest: Hope Stacked Heel Booties $27.99; most expensive: Thane Block Heel "
             "Riding Boots $48.99; best rated: Hope booties 5.0 with 2 reviews; most reviewed: "
             "Inca Suede Loafers 3.8 with 8 reviews; breakdown 5 stars: 2, 1 star: 0.")
    verdict = run_verifier(12, run.root)
    assert verdict.get("pass") is False


def test_tampered_seed_fails(tmp_path):
    """An initial.db that is not the frozen seed must fail the snapshot contract."""
    run = build_run(tmp_path, "tamperedseed", "JCPenney--12")
    mutate_db(_acquire_seed(), run.root / "initial.db",
              [("UPDATE products SET price = 1.23 WHERE id = 1", ())])
    copy_db(_acquire_seed(), run.root / "after.db")
    run.step(HOPE, "goto", {})
    run.done("Cheapest: Hope Stacked Heel Booties $27.99; most expensive: Thane Block Heel "
             "Riding Boots $48.99; best rated: Hope booties 5.0 with 2 reviews; most reviewed: "
             "Inca Suede Loafers 3.8 with 8 reviews; breakdown 5 stars: 2, 1 star: 0.")
    verdict = run_verifier(12, run.root)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True, "snapshot contract violation is fail-closed"


def test_missing_dbs_fail_closed(tmp_path, monkeypatch):
    run = build_run(tmp_path, "nodbs", "JCPenney--12")
    run.step(HOPE, "goto", {})
    run.done("Cheapest: Hope Stacked Heel Booties $27.99; most expensive: Thane Block Heel "
             "Riding Boots $48.99; best rated: Hope booties 5.0 with 2 reviews; most reviewed: "
             "Inca Suede Loafers 3.8 with 8 reviews; breakdown 5 stars: 2, 1 star: 0.")
    monkeypatch.setenv("WH_CONTAINER", "wh-rev-jcp-definitely-not-running")
    verdict = run_verifier(12, run.root)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True


def test_stateful_t3_tampered_seed_fails(tmp_path):
    run = build_run(tmp_path, "t3tampered", "JCPenney--3")
    mutate_db(_acquire_seed(), run.root / "initial.db",
              [("UPDATE cart_items SET quantity = 5 WHERE user_id = 1", ())])
    mutate_db(_acquire_seed(), run.root / "after.db", stateful_statements(3))
    for path, action, params in honest_steps(3):
        run.step(path, action, params)
    run.done(HONEST_ANSWERS["3"])
    verdict = run_verifier(3, run.root)
    assert verdict.get("pass") is False, "a non-seed initial DB must fail the contract"
