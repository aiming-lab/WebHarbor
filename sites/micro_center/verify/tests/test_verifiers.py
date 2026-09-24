"""Deterministic verifier contract tests for the 18 Micro Center tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair — search_log appends allowed; stateful tasks against the seed
with the exact allowed sqlite delta); a no-op run (homepage only, empty
answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct
answer, homepage-only navigation) MUST FAIL; stateful tasks MUST FAIL on a
state-mismatch (clean DB) and on a wrong delta (collateral write); package
tampering (task_id mismatch, off-site URL, missing screenshot, non-done
trajectory) MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, mutate_db, noop_run, run_verifier)

STATEFUL = {0, 3, 4, 5, 7, 8, 10, 11, 13, 14}
READ_ONLY = sorted(set(range(18)) - STATEFUL)
CREATED = "2026-09-24 12:00:00.000000"
PLACED = "2026-09-24 11:00:00.000000"


def _seed():
    return _acquire_seed()


def _search_log_rows():
    return [("INSERT INTO search_log (query, scope, result_count, created_at) "
             "VALUES (?, 'search', 24, ?)", ("laptop", CREATED)),
            ("INSERT INTO search_log (query, scope, result_count, created_at) "
             "VALUES (?, 'search', 24, ?)", ("monitor", CREATED))]


# ---------------------------------------------------------------- honest fixtures
def honest_run(tmp: Path, idx: int):
    """Build the honest run + (initial, after) DB pair for task idx."""
    seed = _seed()
    task_id = f"Micro Center--{idx}"
    root = tmp / f"honest_{idx:02d}"
    b = build_run(tmp, f"honest_{idx:02d}", task_id)
    after = tmp / f"after_{idx:02d}.db"

    def with_search_log(extra=None):
        return mutate_db(seed, after, _search_log_rows() + list(extra or []))

    if idx == 0:
        items = json.dumps([
            {"product_id": 635731, "name": "Smart Glove Wrist Support, Large Size",
             "sku": 1, "price": 21.99, "qty": 1, "brand": "X"},
            {"product_id": 648739, "name": "iFixit Pro Toolkit", "sku": 2,
             "price": 79.99, "qty": 1, "brand": "X"},
            {"product_id": 657262, "name": "1.75mm PLA+ Yellow", "sku": 3,
             "price": 18.99, "qty": 1, "brand": "X"},
            {"product_id": 676305, "name": "Aspire 3 A315-24PT-R1L8 15.6 Touchscreen "
             "Laptop Computer", "sku": 4, "price": 399.99, "qty": 1, "brand": "Acer"},
        ])
        with_search_log([
            ("DELETE FROM cart_items WHERE user_id = 1", ()),
            ("INSERT INTO orders (order_number, user_id, status, method, store_id, "
             "ship_to, payment, placed_at, subtotal, tax, shipping_fee, total, "
             "items_json, created_at) VALUES ('MC2609241234', 1, 'Processing', "
             "'pickup', '085', '', 'Visa ending in 4242', ?, 520.96, 37.77, 0.0, "
             "558.73, ?, ?)", (PLACED, items, CREATED)),
        ])
        b.login("alice.j@test.com")
        b.step("/site/stores/default.aspx", "goto", {})
        b.search("laptop")
        b.product(676305, "aspire-3")
        b.step("/cart", "goto", {})
        b.step("/checkout/mode", "goto", {})
        b.step("/checkout/pickup", "goto", {})
        b.step("/checkout/payment", "goto", {})
        b.step("/checkout/review", "goto", {})
        b.step("/checkout/confirmation?order=MC2609241234", "goto", {})
        b.done("Picked up at Rockville: order MC2609241234, total $558.73 "
               "(Aspire 3 A315-24PT $399.99).",
               final_path="/checkout/confirmation")
    elif idx == 1:
        copy_db(seed, after)
        with_search_log()
        b.search("AM5 motherboard")
        b.product(668914, "a620i-ax")
        b.product(685029, "b650-gaming-x-ax-v2")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.search("32GB DDR5-6000")
        b.product(664095, "ripjaws-s5")
        b.search("RTX")
        b.product(689783, "rtx-3050-windforce")
        b.step("/cart", "goto", {})
        b.done("Combined subtotal before tax: $480.96. The motherboard is the Gigabyte A620I AX "
               "(AM5 socket, better-rated 4.2 vs 4.1 on the compare page). The Ripjaws S5 32GB "
               "DDR5-6000 kit (qty 2) is in stock at 26 of 30 stores.")
    elif idx == 2:
        with_search_log()
        b.step("/site/products/open-box.aspx", "goto", {})
        b.product(671164, "precision-7780")
        b.product(681059, "surface-laptop-zgq")
        b.done("Winner: Dell Precision 7780 Mobile Workstation 17.3\" — new $3,219.99, "
               "Excellent $2,720.96 (saves $499.03). Runner-up: Microsoft Surface Laptop 7th "
               "Edition ZGQ-00001 — new $1,399.99, Excellent $1,019.01 (saves $380.98). The "
               "Precision 7780's open-box conditions: Excellent $2,720.96, Satisfactory $2,714.66. "
               "It is in stock at 23 of 30 stores and is NOT in stock at the Cambridge, MA store "
               "(out of stock there).")
    elif idx == 3:
        items = json.dumps([
            {"product_id": 638748, "name": "Smart Business Pack (PC)", "sku": 1,
             "price": 29.99, "qty": 1, "brand": "X"},
            {"product_id": 651144, "name": "Wireless Mouse M185 - Blue", "sku": 2,
             "price": 17.99, "qty": 1, "brand": "X"},
            {"product_id": 641955, "name": "NVIDIA GeForce GT 730 Low Profile",
             "sku": 3, "price": 79.99, "qty": 1, "brand": "ASUS"},
        ])
        with_search_log([
            ("DELETE FROM cart_items WHERE user_id = 2", ()),
            ("INSERT INTO orders (order_number, user_id, status, method, store_id, "
             "ship_to, payment, placed_at, subtotal, tax, shipping_fee, total, "
             "items_json, created_at) VALUES ('MC2609247168', 2, 'Processing', "
             "'pickup', '131', '', 'Visa ending in 4242', ?, 127.97, 9.28, 0.0, "
             "137.25, ?, ?)", (PLACED, items, CREATED)),
        ])
        b.login("bob.c@test.com")
        b.search("graphics card")
        b.product(641955, "geforce-gt-730")
        b.step("/cart", "goto", {})
        b.step("/checkout/mode", "goto", {})
        b.step("/checkout/pickup", "goto", {})
        b.step("/checkout/payment", "goto", {})
        b.step("/checkout/review", "goto", {})
        b.step("/checkout/confirmation?order=MC2609247168", "goto", {})
        b.done("Reserved MC2609247168 for pickup at Dallas (GT 730 $79.99, in stock "
               "at both Dallas and Houston), total $137.25.",
               final_path="/checkout/confirmation")
    elif idx == 4:
        with_search_log([
            ("UPDATE orders SET status = 'Cancelled' WHERE order_number = 'MC2608231112'", ()),
            ("DELETE FROM cart_items WHERE id = 7", ()),
            ("UPDATE cart_items SET qty = 1 WHERE id = 6", ()),
        ])
        b.login("carol.d@test.com")
        b.step("/account/orders", "goto", {})
        b.step("/account/orders/MC2608231112", "goto", {})
        b.product(676998, "qn55s85daexza")
        b.product(678427, "legion-pro-7")
        b.step("/account/payments", "goto", {})
        b.step("/account/orders/MC2608231112", "goto", {})
        b.step("/cart", "goto", {})
        b.done("Cancelled order MC2608231112 (both items still in stock at Austin). Status now: "
               "Cancelled; refund total $4,034.84. It was paid with the saved Visa ending in "
               "4333. Reworked cart: removed the 64XL Black Ink Cartridge and set Art Explosion "
               "to qty 1; new subtotal $74.98.")
    elif idx == 5:
        with_search_log([
            ("DELETE FROM list_items WHERE id IN (13, 14)", ()),
            ("INSERT INTO list_items (user_id, product_id, note, created_at) "
             "VALUES (3, 702087, '', ?)", (CREATED,)),
            ("INSERT INTO compare_items (user_id, product_id, created_at) "
             "VALUES (3, 702087, ?)", (CREATED,)),
            ("INSERT INTO compare_items (user_id, product_id, created_at) "
             "VALUES (3, 690495, ?)", (CREATED,)),
        ])
        b.login("carol.d@test.com")
        b.search("wireless mechanical keyboard")
        b.product(702087, "c75-cake-meow")
        b.product(690495, "retro-87-key-xbox")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.step("/account/lists", "goto", {})
        b.done("I kept the C75 Cake Meow Wireless Mechanical Keyboard ($91.99, better-rated 4.7 "
               "vs 3.7). After removing the two most expensive items (Combo Touch, Corsair "
               "RM850e), the list has 3 items: NVIDIA GeForce GT 730, Inland Power Strip VPR "
               "500, and the C75 Cake Meow Keyboard.")
    elif idx == 6:
        with_search_log()
        b.search("27 inch monitor")
        b.product(683850, "27cl1-gbi")
        b.product(664856, "27mq450-b")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.step("/store/085", "goto", {})
        b.step("/cart", "goto", {})
        b.done("The 27CL1 Gbi ($89.99) has the higher refresh rate: 120Hz vs 75Hz on the "
               "27MQ450-B ($119.99). The 27CL1 is in stock at 24 stores, the 27MQ450-B at 25 "
               "stores. The 27CL1 is in stock at Rockville, MD (my store). Two units: subtotal "
               "$179.98, estimated tax $13.05.")
    elif idx == 7:
        with_search_log([
            ("UPDATE users SET phone = '919-555-0142' WHERE id = 1", ()),
            ("UPDATE addresses SET is_default = 0 WHERE id = 1", ()),
            ("INSERT INTO addresses (user_id, label, full_name, line1, line2, city, "
             "state, zip_code, phone, is_default) VALUES (1, 'Shipping', 'Dana Johnson', "
             "'730 Memorial Drive', 'Apt 5B', 'Cambridge', 'MA', '02139', "
             "'617-555-8890', 1)", ()),
        ])
        b.login("alice.j@test.com")
        b.step("/account/profile", "goto", {})
        b.step("/account/addresses", "goto", {})
        b.done("Phone updated to 919-555-0142. New default address: Dana Johnson, 730 "
               "Memorial Drive, Apt 5B, Cambridge, MA 02139.")
    elif idx == 8:
        items = json.dumps([
            {"product_id": 325743, "name": "Advance CF-12LB Long Life Bearing 120mm "
             "Case Fan", "sku": 1, "price": 7.99, "qty": 2, "brand": "X"},
        ])
        ship_to = json.dumps({"full_name": "Dana Chen", "line1": "350 Fifth Avenue",
                              "line2": "", "city": "New York", "state": "NY",
                              "zip": "10118"})
        with_search_log([
            ("INSERT INTO orders (order_number, user_id, status, method, store_id, "
             "ship_to, payment, placed_at, subtotal, tax, shipping_fee, total, "
             "items_json, created_at) VALUES ('MC2609248092', 0, 'Preparing to Ship', "
             "'shipping', NULL, ?, 'Visa ending in 4242', ?, 15.98, 1.16, 12.99, "
             "30.13, ?, ?)", (ship_to, PLACED, items, CREATED)),
        ])
        b.search("120mm case fan")
        b.product(325743, "advance-cf-12lb")
        b.step("/cart", "goto", {})
        b.step("/checkout/mode", "goto", {})
        b.step("/checkout/shipping", "goto", {})
        b.step("/checkout/payment", "goto", {})
        b.step("/checkout/review", "goto", {})
        b.step("/checkout/confirmation?order=MC2609248092", "goto", {})
        b.done("Guest order MC2609248092 for two Advance CF-12LB fans, shipped "
               "two-day to Dana Chen, 350 Fifth Avenue, New York, NY 10118. "
               "Total $30.13.", final_path="/checkout/confirmation")
    elif idx == 9:
        with_search_log()
        b.search("4TB SSD")
        b.product(674530, "4tb-pcie-gen4-nvme-ps5")
        b.product(676677, "pro-blade-ssd-mag")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.step("/store/155", "goto", {})
        b.product(672227, "purple-4tb-surveillance-hdd")
        b.step("/cart", "goto", {})
        b.done("The PS5-compatible drive is the 4TB PCIe Gen 4 x4 NVMe 3D NAND M.2 Internal "
               "SSD with Heatsink: 4TB, $459.99, PCIe Gen 4 x4 NVMe (M.2). The only Texas Micro "
               "Center with it in stock is Houston, which I set as my store. Added two of them "
               "plus the cheapest 4TB internal hard drive (Purple 4TB, $104.99). Final "
               "subtotal: $1,024.97.")
    elif idx == 10:
        with_search_log([
            ("INSERT INTO reviews (product_id, author, rating, date, title, body, verified) "
             "VALUES (675726, 'David Kim', 4, '2026-09-24', 'Solid purchase', "
             "'It arrived quickly and works well. No complaints at all.', 1)", ()),
            ("INSERT INTO reviews (product_id, author, rating, date, title, body, verified) "
             "VALUES (673901, 'David Kim', 3, '2026-09-24', 'Does the job', "
             "'It is basic but handy to have around the workshop.', 1)", ()),
            ("UPDATE products SET review_count = 184, rating = 4.6 WHERE product_id = 675726", ()),
            ("UPDATE products SET review_count = 120, rating = 4.4 WHERE product_id = 673901", ()),
        ])
        b.login("david.k@test.com")
        b.step("/account/orders", "goto", {})
        b.step("/account/orders/MC2609071148", "goto", {})
        b.product(675726, "unifi-gateway-lite")
        b.product(673901, "plastic-scraper")
        b.done("Order MC2609071148 (pickup at the Tustin, CA store). Posted a 4-star review "
               "'Solid purchase' for the UniFi Gateway Lite — its review count is now 184 — and "
               "a 3-star review 'Does the job' for the Plastic Scraper Handle & Razor Blades — "
               "now 120 reviews.")
    elif idx == 11:
        with_search_log([
            ("INSERT INTO payment_cards (user_id, brand, last4, exp_month, exp_year, "
             "is_default) VALUES (1, 'Mastercard', '5678', '05', '2029', 1)", ()),
            ("INSERT INTO payment_cards (user_id, brand, last4, exp_month, exp_year, "
             "is_default) VALUES (1, 'American Express', '9012', '11', '2027', 0)", ()),
            ("UPDATE payment_cards SET is_default = 0 WHERE id = 1", ()),
            ("DELETE FROM payment_cards WHERE id = 2", ()),
        ])
        b.login("alice.j@test.com")
        b.step("/account/payments", "goto", {})
        b.done("I now have 3 saved payment methods. The default is the new Mastercard ending "
               "in 5678 (exp 05/2029). I removed the old Mastercard ending in 2777; the "
               "American Express ending in 9012 (exp 11/2027) and the Visa ending in 2111 "
               "remain.")
    elif idx == 12:
        with_search_log()
        b.step("/store/105", "goto", {})
        b.search("wireless mouse")
        b.product(627261, "m190-wireless-mouse")
        b.product(697541, "cat-theme-wireless-mouse")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.step("/cart", "goto", {})
        b.done("Yonkers Sunday hours: 11:00 AM - 6:00 PM. The cheapest qualifying mouse is the "
               "Logitech M190 ($17.99); Yonkers has only 3 left, and 26 stores nationwide "
               "stock it. Two of the Cat Theme Wireless Mouse - Fortune ($24.99) are in the "
               "cart; subtotal $49.98.")
    elif idx == 13:
        items = json.dumps([
            {"product_id": 678822, "name": "65UT7570PUB 65 Class 4K Ultra HD Smart "
             "LED TV", "sku": 1, "price": 399.99, "qty": 1, "brand": "LG"},
        ])
        with_search_log([
            ("INSERT INTO orders (order_number, user_id, status, method, store_id, "
             "ship_to, payment, placed_at, subtotal, tax, shipping_fee, total, "
             "items_json, created_at) VALUES ('MC2609244327', 0, 'Processing', "
             "'pickup', '151', '', 'Visa ending in 4242', ?, 399.99, 29.00, 0.0, "
             "428.99, ?, ?)", (PLACED, items, CREATED)),
        ])
        b.search("65 inch TV")
        b.product(678822, "65ut7570pub")
        b.step("/cart", "goto", {})
        b.step("/checkout/mode", "goto", {})
        b.step("/checkout/pickup", "goto", {})
        b.step("/checkout/payment", "goto", {})
        b.step("/checkout/review", "goto", {})
        b.step("/checkout/confirmation?order=MC2609244327", "goto", {})
        b.done("Guest pickup order MC2609244327 at Micro Center Chicago for the "
               "65UT7570PUB 65\" 4K TV ($399.99), total $428.99.",
               final_path="/checkout/confirmation")
    elif idx == 14:
        with_search_log([
            ("INSERT INTO users (email, username, display_name, password_hash, phone, "
             "is_benchmark, created_at) VALUES ('frank.m@test.com', 'frank_m', "
             "'Frank Miller', 'x', '555-555-0100', 0, ?)", (CREATED,)),
            ("INSERT INTO list_items (user_id, product_id, note, created_at) "
             "SELECT id, 676237, '', ? FROM users WHERE email = 'frank.m@test.com'",
             (CREATED,)),
            ("INSERT INTO list_items (user_id, product_id, note, created_at) "
             "SELECT id, 512934, '', ? FROM users WHERE email = 'frank.m@test.com'",
             (CREATED,)),
            ("INSERT INTO list_items (user_id, product_id, note, created_at) "
             "SELECT id, 611534, '', ? FROM users WHERE email = 'frank.m@test.com'",
             (CREATED,)),
            ("INSERT INTO cart_items (user_id, product_id, qty, created_at) "
             "SELECT id, 676237, 1, ? FROM users WHERE email = 'frank.m@test.com'",
             (CREATED,)),
        ])
        b.step("/account/register", "goto", {})
        b.fill("/account/register", "frank.m@test.com", "input[name='email']")
        b.search("Bambu Lab A1")
        b.product(676237, "a1-3d-printer")
        b.step("/cart", "goto", {})
        b.product(512934, "pla-white")
        b.product(611534, "pla-plus-blue")
        b.step("/account/lists", "goto", {})
        b.done("My list has 3 items: the Bambu Lab A1 3D Printer ($359.99), the 1.75mm PLA "
               "filament spool in White ($12.99), and the 1.75mm PLA+ spool in Blue ($14.99). "
               "Filament colors picked: White (PLA) and Blue (PLA+).")
    elif idx == 15:
        with_search_log()
        b.step("/store/115", "goto", {})
        b.search("keyboard")
        b.product(702087, "c75-cake-meow")
        b.search("mouse")
        b.product(613558, "raspberry-pi-mouse")
        b.search("monitor")
        b.product(667603, "acer-22cv1q")
        b.search("USB hub")
        b.product(612948, "4-port-usb3-hub")
        b.step("/cart", "goto", {})
        b.done("Cheapest qualifying combination, all in stock at Brooklyn — subtotal $181.96: "
               "C75 Cake Meow Wireless Mechanical Keyboard ($91.99), Official Raspberry Pi "
               "Optical USB Mouse ($7.99), Acer 22CV1Q 21.5\" Monitor ($69.99), and the "
               "4-Port USB 3.0 Type-A HUB ($11.99).")
    elif idx == 16:
        with_search_log()
        b.step("/store/085", "goto", {})
        b.search("32GB DDR5-6000 RGB")
        b.product(685119, "ares-rgb-32gb-ddr5-6000")
        b.step("/endeca/CompareV2.aspx", "goto", {})
        b.product(664095, "ripjaws-s5")
        b.step("/cart", "goto", {})
        b.done("My kit: Lexar ARES RGB 32GB DDR5-6000 ($94.99) — spec sheet: CAS latency 30, "
               "memory timings 30-36-36-68, voltage 1.35V; it is in stock at 25 of 30 stores "
               "and at Rockville. My friend's kit: Ripjaws S5 32GB DDR5-6000 ($82.99), also in "
               "stock at Rockville. Both added to the cart; subtotal $177.98.")
    elif idx == 17:
        with_search_log()
        b.step("/store/121", "goto", {})
        b.search("Bambu Lab A1")
        b.product(676237, "a1-3d-printer")
        b.product(512934, "pla-white")
        b.product(611534, "pla-plus-blue")
        b.step("/cart", "goto", {})
        b.done("Starter order: Bambu Lab A1 3D Printer ($359.99) + two spools of 1.75mm PLA "
               "filament in White ($12.99 each) + one 1.75mm PLA+ spool in Blue ($14.99). The "
               "plain PLA's recommended plate temperature from its spec sheet is 60°C - 80°C. "
               "Subtotal $400.96. Filament colors: White and Blue.")
    else:
        raise AssertionError(idx)

    return root, seed, after


HONEST_ANSWERS = {}  # filled lazily below via honest_run()


# ---------------------------------------------------------------- test batteries
@pytest.mark.parametrize("idx", range(18))
def test_honest_pass(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 0 and payload["pass"] is True, json.dumps(payload, indent=1)[:2000]


@pytest.mark.parametrize("idx", range(18))
def test_noop_fail(tmp_path, idx):
    seed = _seed()
    root = noop_run(tmp_path, f"noop_{idx:02d}", f"Micro Center--{idx}")
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, seed)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_wrong_answer_fail(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = "I did the thing and the answer is 42 and MC0000000000."
    (root / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_shortcut_fail(tmp_path, idx):
    """Correct answer, homepage-only navigation: knowledge-recall shortcut."""
    root, seed, after = honest_run(tmp_path, idx)
    traj = json.loads((root / "trajectory.json").read_text())
    for step in traj["steps"]:
        step["url"] = BASE + "/"
        step.pop("url_after", None)
    traj["final_url"] = BASE + "/"
    (root / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", sorted(STATEFUL))
def test_state_mismatch_fail(tmp_path, idx):
    """Agent self-reports success but the DB is unchanged."""
    seed = _seed()
    root, _, after = honest_run(tmp_path, idx)
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, seed)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", sorted(STATEFUL))
def test_wrong_delta_fail(tmp_path, idx):
    """The allowed delta happened, but so did a collateral write (to a table
    outside every task's allowed set)."""
    root, seed, after = honest_run(tmp_path, idx)
    con = sqlite3.connect(str(after))
    con.execute("INSERT INTO search_log (query, scope, result_count, created_at) "
                "VALUES ('x', 'search', 1, '2026-09-24 12:00:00.000000')")
    con.execute("INSERT INTO compare_items (user_id, product_id, created_at) "
                "VALUES (1, 674530, '2026-09-24 12:00:00.000000')")  # collateral, never allowed
    con.commit()
    con.close()
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", sorted(READ_ONLY))
def test_read_only_mutation_fail(tmp_path, idx):
    """Read-only tasks fail when the DB was mutated beyond search_log."""
    root, seed, after = honest_run(tmp_path, idx)
    con = sqlite3.connect(str(after))
    con.execute("UPDATE products SET price = price + 1 WHERE product_id = 674530")
    con.execute("INSERT INTO list_items (user_id, product_id, note, created_at) "
                "VALUES (1, 674530, '', '2026-09-24 12:00:00.000000')")
    con.commit()
    con.close()
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_tamper_task_id_fail(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["task_id"] = "Micro Center--99"
    (root / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_tamper_offsite_url_fail(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://example.com/phish"
    (root / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_tamper_missing_screenshot_fail(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    shot = root / "screenshots" / "step_001.png"
    if shot.is_file():
        shot.unlink()
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


@pytest.mark.parametrize("idx", range(18))
def test_tamper_not_done_fail(tmp_path, idx):
    root, seed, after = honest_run(tmp_path, idx)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (root / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, payload = run_verifier(f"Micro Center--{idx}", root, seed, after)
    assert code == 1 and payload["pass"] is False, payload


def test_tasks_jsonl_contract():
    tasks = Path(__file__).resolve().parents[2] / "tasks.jsonl"
    rows = [json.loads(l) for l in tasks.read_text().splitlines()]
    assert len(rows) == 18
    for row in rows:
        idx = int(row["id"].split("--")[1])
        assert row["verifier_path"] == f"sites/micro_center/verify/verify_{idx}.py"
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS:")
        assert "answer" not in row
        assert list(row.keys())[:5] == ["web_name", "id", "ques", "web", "upstream_url"]
