"""Deterministic verifier contract tests for the 30 JCPenney tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a clean
seed pair; stateful tasks against the seed with the exact allowed sqlite delta);
a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a wrong answer MUST
FAIL; a shortcut (correct answer, homepage-only navigation) MUST FAIL — every task's
required surface is beyond the homepage. Read-only tasks MUST FAIL on a mutated
after-DB; stateful tasks MUST FAIL on a state-mismatch (no DB delta) and on a wrong
delta. Package tampering (task_id mismatch, off-site URLs, missing screenshots,
non-done trajectory, tampered seed, unavailable DB) MUST fail closed.

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

STATEFUL = {8, 12, 19, 20, 21, 22}
READ_ONLY = sorted(set(range(30)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}

BULOVA = "/p/bulova-crystal-womens-crystal-accent-two-tone-stainless-steel-bracelet-watch-98l273/ppr5007888050"
SHEET = "/p/casual-comfort-premium-ultra-soft-microfiber-wrinkle-free-6-piece-sheet-set/ppr5007323303"
ANA = "/p/a-n-a-womens-crew-neck-long-sleeve-t-shirt/ppr5008726636"
KAYLEY = "/p/pop-womens-kayley-flat-heel-slouch-boots/ppr5008672777"
FRYE = "/p/frye-and-co-womens-miranda-stacked-heel-riding-boots/ppr5008625370"
LIOTTA = "/p/pop-womens-liotta-flat-heel-motorcycle-boots/ppr5008672778"
MAXBLACKOUT = "/p/max-blackout-mystique-grommet-top-100-blackout-single-curtain-panel/ppr5007989193"
PAPELL = "/p/papell-boutique-womens-v-neck-short-sleeve-cap-evening-gown/ppr5008618161"
CREATED = "2026-09-22 00:00:00.000000"
HASH = "jcpenney-webharbor-demo:"


def pw_hash(raw: str) -> str:
    import hashlib
    return hashlib.sha256(f"{HASH}{raw}".encode()).hexdigest()


# ---------------------------------------------------------------- navigation fixtures
def honest_steps(index: int):
    """[(path, action, params)] navigation for the honest run of task `index`."""
    def login(who):
        return [("/signin", "fill", {"text": LOGIN[who], "selector": "input[name=email]"}),
                ("/signin", "fill", {"text": PASSWORD, "selector": "input[name=password]"}),
                ("/signin", "click", {"selector": "button[type=submit]"}, )]
    S = {
        0: [("/s/boots?sortBy=price_low", "goto", {})],
        1: [("/s/blackout%20curtain%20panel", "goto", {}), (MAXBLACKOUT, "goto", {})],
        2: [("/g/home-store/all-bedding?brand=liz+claiborne", "goto", {})],
        3: [(BULOVA, "goto", {})],
        4: [(SHEET, "goto", {})],
        5: [(ANA, "goto", {})],
        6: [(KAYLEY, "goto", {}), ("/cart", "goto", {})],
        7: [("/signin", "fill", {"text": LOGIN["alice"], "selector": "input[name=email]"}),
            ("/signin", "fill", {"text": PASSWORD, "selector": "input[name=password]"}),
            ("/signin", "click", {"selector": "button[type=submit]"}),
            ("/cart", "goto", {})],
        8: login("alice") + [("/checkout/shipping", "goto", {}),
                             ("/checkout/payment", "goto", {}),
                             ("/checkout/review", "goto", {}),
                             ("/checkout/confirmation/JCP123456001", "goto", {})],
        9: login("bob") + [("/account/dashboard/orders", "goto", {}),
                           ("/orders/JCP2609131004", "goto", {})],
        10: [("/orders", "goto", {})],
        11: login("carol") + [("/account/dashboard/wishlist", "goto", {})],
        12: login("alice") + [("/account/dashboard/wishlist", "goto", {})],
        13: login("david") + [("/account/dashboard/rewards", "goto", {})],
        14: [("/m/jcpenney-coupons", "goto", {})],
        15: [("/m/jcpenney-coupons", "goto", {})],
        16: [("/gift-cards", "goto", {})],
        17: [("/stores?state=WA", "goto", {})],
        18: [("/stores/2011", "goto", {})],
        19: [("/register", "goto", {}),
             ("/signin", "fill", {"text": "honest.t19runner@example.com", "selector": "input[name=email]"}),
             ("/signin", "fill", {"text": "Shopper123!", "selector": "input[name=password]"}),
             ("/signin", "click", {"selector": "button[type=submit]"}),
             ("/account/dashboard", "goto", {})],
        20: login("alice") + [("/account/dashboard/profile", "goto", {})],
        21: login("bob") + [("/account/dashboard/profile", "goto", {})],
        22: login("carol") + [("/account/dashboard/profile", "goto", {}),
                              ("/signin", "fill", {"text": LOGIN["carol"], "selector": "input[name=email]"}),
                              ("/signin", "fill", {"text": "AutumnWalk45!", "selector": "input[name=password]"}),
                              ("/signin", "click", {"selector": "button[type=submit]"}),],
        23: [("/g/women/womens-plus-size", "goto", {})],
        24: [("/g/new-and-trending", "goto", {})],
        25: [("/g/shops/halloween-shop", "goto", {})],
        26: [("/", "goto", {}), ("/g/shoes/all-womens-shoes", "goto", {})],
        27: [(FRYE, "goto", {}), (LIOTTA, "goto", {})],
        28: login("alice") + [("/account/dashboard/orders", "goto", {}),
                             ("/orders/JCP2609190003", "goto", {})],
        29: login("david") + [("/account/dashboard/orders", "goto", {}),
                              ("/orders/JCP2609203008", "goto", {}),
                              (PAPELL, "goto", {})],
    }
    return S[index]


# ---------------------------------------------------------------- stateful mutations
def stateful_statements(index: int, variant: str = "ok"):
    """[(sql, params)] turning a seed copy into the honest after-state (or a wrong one)."""
    if index == 8:
        # honest = post-F3 arithmetic (tax on the discounted subtotal);
        # wrong_amounts = the pre-fix arithmetic (tax on the pre-discount subtotal)
        if variant == "wrong_amounts":
            total, tax, discount = 62.93, 5.69, 20.70
        else:
            total, tax, discount = 61.22, 3.98, 20.70
        order_sql = (
            "INSERT INTO orders (id, order_number, user_id, email, status, placed_at, delivered_at, "
            "subtotal, discount, shipping, tax, total, coupon_code, ship_name, ship_address, ship_city, "
            "ship_state, ship_zip, ship_phone, payment_type, payment_last4, tracking_number, carrier, "
            "pickup_store, gift_message, created_at) VALUES (9, 'JCP123456001', 1, 'alice.j@test.com', "
            "'Processing', '2026-09-23 12:34:56', NULL, 68.99, ?, 8.95, ?, ?, 'SAVE30', 'Alice Johnson', "
            "'1460 Alderwood Mall Blvd', 'Lynnwood', 'WA', '98037', '(206) 555-0147', 'Visa', '4242', "
            "'', '', NULL, '', ?)")
        items = [
            ("INSERT INTO order_items (id, order_id, product_id, product_name, brand, color, size, "
             "quantity, unit_price, image_file, created_at) VALUES (15, 9, 61, 'Arizona Mens Hooded Long "
             "Sleeve Classic Fit Big and Tall Twofer Flannel Shirt', 'Arizona Jean Co', 'Sidney Plaid', "
             "'2x-large', 1, 31.49, 'p1.jpg', ?)", (CREATED,)),
            ("INSERT INTO order_items (id, order_id, product_id, product_name, brand, color, size, "
             "quantity, unit_price, image_file, created_at) VALUES (16, 9, 53, 'PUMA Sweatpants Mens "
             "Straight Mid Rise Regular Fit Fleece Active Jogger Pant', 'Puma', 'Mouse Gray', 'small', "
             "1, 37.50, 'p2.jpg', ?)", (CREATED,)),
        ]
        return [(order_sql, (discount, tax, total, CREATED)), *items,
                ("DELETE FROM cart_items WHERE user_id = 1", ())]
    if index == 12:
        pid = 34 if variant == "wrong_row" else 11
        return [(f"DELETE FROM wishlist_items WHERE user_id = 1 AND product_id = {pid}", ())]
    if index == 19:
        pwhash = pw_hash("WrongPass1!") if variant == "wrong_hash" else pw_hash("Shopper123!")
        return [("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
                 "rewards_member, rewards_points, rewards_tier, created_at) VALUES (5, "
                 "'honest.t19runner@example.com', ?, 'Honest', 'Runner', '', 0, 0, '', ?)", (pwhash, CREATED))]
    if index == 20:
        uid = 2 if variant == "wrong_user" else 1
        return [("INSERT INTO addresses (id, user_id, label, first_name, last_name, line1, line2, "
                 "city, state, zip, phone, is_default, created_at) VALUES (7, ?, '', 'Alex', 'Johnson', "
                 "'582 Rainier Ave S', '', 'Seattle', 'WA', '98144', '(206) 555-0147', 0, ?)",
                 (uid, CREATED))]
    if index == 21:
        last4 = "9999" if variant == "wrong_card" else "1155"
        return [("INSERT INTO payment_methods (id, user_id, card_type, last4, cardholder, exp_month, "
                 "exp_year, is_default, created_at) VALUES (6, 2, 'Visa', ?, 'Bob Chen', 8, 2029, 0, ?)",
                 (last4, CREATED))]
    if index == 22:
        pwhash = pw_hash("WrongPass1!") if variant == "wrong_hash" else pw_hash("AutumnWalk45!")
        return [("UPDATE users SET password_hash = ? WHERE email = 'carol.d@test.com'", (pwhash,))]
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
@pytest.mark.parametrize("index", range(30))
def test_honest_passes(tmp_path, index):
    run_dir = make_honest(tmp_path, index, db_pair="stateful" if index in STATEFUL else "clean")
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is True, f"honest run failed: {json.dumps(verdict)[:600]}"


@pytest.mark.parametrize("index", range(30))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "no-op run must fail"
    assert verdict.get("reason"), "no-op failure must carry a reason"


@pytest.mark.parametrize("index", range(30))
def test_wrong_answer_fails(tmp_path, index):
    run_dir = make_honest(tmp_path, index, db_pair="stateful" if index in STATEFUL else "clean")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    wrong = {
        0: "The boots search returns 5 results; the cheapest is the Pop Liotta boots at $19.99.",
        1: "The most expensive Blackout product is the Regal Home Arlo panel at $21.00-$65.00, "
           "original $99.99, with 3 swatches.",
        2: "LIZ CLAIBORNE has 4 bedding products; the most expensive is the Ultra Fit 575TC at "
           "$34.99 - $180.",
        3: "The Bulova watch costs $187.50 (original $500), rated 3.2 with 12 reviews; 5-star: 9, "
           "1-star: 3.",
        4: "The set includes 1 flat sheet 39x76 and 1 pillowcase; features: machine washable, cotton.",
        5: "The A.N.A t-shirt is rated 4.8 with 21 reviews; the most recent review is 'Runs large' "
           "at 2 stars.",
        6: "The bag subtotal is $89.00, shipping is FREE, and the estimated tax is $12.34.",
        7: "The bag has 3 items: a Levi's jacket at $52.00 and boots at $140.00; subtotal $192.00, "
           "tax $15.82.",
        8: "The new order number is ORDER-999, the discount is $45.00, and the total is $99.99.",
        9: "Order JCPOLD12345 is Cancelled, shipped via FedEx, tracking 999999; it contains a "
           "Levi's jacket at $88.00.",
        10: "Order JCP2609021005 is Delivered via UPS; it contains a Biolage shampoo and a bra.",
        11: "The wish list has 9 items: a St. John's Bay parka at $112.00 and a Frye boot at $140.00.",
        12: "After the removal 7 items remain, including the London Times jumpsuit and a "
           "Bulova watch.",
        13: "The balance is 1,204 points, tier Rewards Access; the latest activity is a Welcome "
           "bonus of 500 pts on December 3, 2026.",
        14: "The coupons are SAVE30 (through Dec 1, 2026), AUTUMN, WATCH20, BRIDE40, GOSHOP15 and "
           "SNEAK25; SNEAK25 stays valid the longest.",
        15: "The minimum-purchase coupon is AUTUMN: 25% off with a $75 minimum; exclusions: "
           "'Select brands excluded.'",
        16: "The gift card balance is $84.50 and it doubles on the second check.",
        17: "Washington has 4 stores; the Lynnwood store is at Seattle Premium Outlets, phone "
           "(206) 555-0000.",
        18: "Store #2011 is at 1 Main Street, Seattle; Sunday hours 9:00-17:00; services: Salon.",
        19: "I registered with email honest.t19runner@example.com and the dashboard shows 'Hello, "
           "Someone Else'.",
        20: "The profile now lists 5 addresses and the new one is the default.",
        21: "There are now 4 payment methods and the Visa 1155 is the default.",
        22: "The old password still works and the new one is rejected; nothing changed.",
        23: "Plus Size lists 12 products by Arizona and Okie Dokie; the most expensive is $99.00.",
        24: "New & Trending shows 40 products; cheapest is a candle at $12.99; most expensive is "
           "a watch at $295.00.",
        25: "The Halloween Shop lists 9 products; cheapest $14.99; most expensive $119.00.",
        26: "The cheapest women's shoe is $19.99 (Arizona sneakers) and the homepage claim matches.",
        27: "The Pop Liotta boots are rated higher at 4.5 with 9 reviews vs the Frye 3.1 with "
           "4 reviews; the price difference is $12.00.",
        28: "The error message is 'Wrong credentials'; the newest order is JCP2609100001, "
           "Delivered, tracking 1ZOLD.",
        29: "The order with the sweater dress is JCP2609203009, status Delivered, total $99.99; "
           "the Papell gown costs $250.00 - $400.00.",
    }[index]
    traj["final_answer"] = wrong
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert verdict.get("pass") is False, "wrong answer must fail"


@pytest.mark.parametrize("index", range(30))
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
        0: ("UPDATE products SET price = price + 1 WHERE id = 1", ()),
        3: ("UPDATE reviews SET rating = 1 WHERE id = 1", ()),
        5: ("UPDATE reviews SET headline = 'tampered' WHERE id = 1", ()),
        9: ("UPDATE orders SET status = 'Cancelled' WHERE order_number = 'JCP2609131004'", ()),
        11: ("DELETE FROM wishlist_items WHERE id = 8", ()),
        14: ("UPDATE coupons SET valid_through = 'never' WHERE code = 'SAVE30'", ()),
        17: ("UPDATE stores SET phone = '555-0000' WHERE number = 2011", ()),
        24: ("UPDATE categories SET name = 'Tampered' WHERE slug = 'new-and-trending'", ()),
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
    (8, "wrong_amounts"), (12, "wrong_row"), (19, "wrong_hash"),
    (20, "wrong_user"), (21, "wrong_card"), (22, "wrong_hash"),
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
    run_dir = make_honest(tmp_path, 3)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "JCPenney--29"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(3, run_dir)
    assert verdict.get("pass") is False


def test_offsite_urls_fail(tmp_path):
    run = build_run(tmp_path, "offsite", "JCPenney--3")
    copy_db(_acquire_seed(), run.root / "initial.db")
    copy_db(_acquire_seed(), run.root / "after.db")
    run.step("https://example.com/product", "goto", {}, url="https://example.com/product")
    run.step(BULOVA, "goto", {})
    run.done("The Bulova watch costs $150.00 - $375.00, rated 4.5 with 8 reviews.")
    verdict = run_verifier(3, run.root)
    assert verdict.get("pass") is False, "off-site URL must break the local-origin gate"


def test_missing_screenshot_fails(tmp_path):
    run_dir = make_honest(tmp_path, 3)
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(3, run_dir)
    assert verdict.get("pass") is False


def test_terminated_false_fails(tmp_path):
    run_dir = make_honest(tmp_path, 3)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(3, run_dir)
    assert verdict.get("pass") is False


def test_empty_steps_fail(tmp_path):
    run = build_run(tmp_path, "nosteps", "JCPenney--3")
    copy_db(_acquire_seed(), run.root / "initial.db")
    copy_db(_acquire_seed(), run.root / "after.db")
    run.steps = []
    run.done("The Bulova watch costs $150.00 - $375.00, rated 4.5 with 8 reviews.")
    verdict = run_verifier(3, run.root)
    assert verdict.get("pass") is False


def test_tampered_seed_fails(tmp_path):
    """An initial.db that is not the frozen seed must fail the snapshot contract."""
    run = build_run(tmp_path, "tamperedseed", "JCPenney--3")
    mutate_db(_acquire_seed(), run.root / "initial.db",
              [("UPDATE products SET price = 1.23 WHERE id = 1", ())])
    copy_db(_acquire_seed(), run.root / "after.db")
    run.step(BULOVA, "goto", {})
    run.done("The Bulova watch costs $150.00 - $375.00, rated 4.5 with 8 reviews.")
    verdict = run_verifier(3, run.root)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True, "snapshot contract violation is fail-closed"


def test_missing_dbs_fail_closed(tmp_path, monkeypatch):
    run = build_run(tmp_path, "nodbs", "JCPenney--3")
    run.step(BULOVA, "goto", {})
    run.done("The Bulova watch costs $150.00 - $375.00, rated 4.5 with 8 reviews.")
    monkeypatch.setenv("WH_CONTAINER", "wh-rev-jcp-definitely-not-running")
    verdict = run_verifier(3, run.root)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True


def test_stateful_t8_tampered_seed_fails(tmp_path):
    run = build_run(tmp_path, "t8tampered", "JCPenney--8")
    mutate_db(_acquire_seed(), run.root / "initial.db",
              [("UPDATE cart_items SET quantity = 5 WHERE user_id = 1", ())])
    mutate_db(_acquire_seed(), run.root / "after.db", stateful_statements(8))
    for path, action, params in honest_steps(8):
        run.step(path, action, params)
    run.done(HONEST_ANSWERS["8"])
    verdict = run_verifier(8, run.root)
    assert verdict.get("pass") is False, "a non-seed initial DB must fail the contract"
