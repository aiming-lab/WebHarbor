"""Deterministic verifier contract tests for the 30 macys_wine_shop tasks.

Covers, per task: the honest trajectory MUST PASS (for the four tasks the live mirror
currently blocks — 3/5/6 hit the collection sort no-op defect, 27 the missing gift-card
amount selector — the fixtures simulate the compliant post-fix state, documenting the
contract, exactly like the instructure T24 precedent); a no-op run (homepage only, empty
answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer,
homepage-only navigation) MUST FAIL for every task (all 30 required surfaces are beyond
the homepage). Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks
(13/15/16/24) MUST FAIL on a state-mismatch (no DB delta) and on a wrong state delta.
Package tampering (task_id mismatch, off-site URLs, missing screenshots, non-done
trajectory, tampered seed, unavailable DB) MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are hand-written
in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, SEED_DB, _acquire_seed, build_run, copy_db,  # noqa: E402
                      mutate_db, noop_run, run_verifier)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file() and not _acquire_seed().is_file() and False,
                                reason="seed DB unavailable")

STATEFUL = {13, 15, 16, 24}
READ_ONLY = sorted(set(range(30)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}

TIMETIDE = "/products/2023-time-tide-chardonnay-monterey-county"
VALANDA = "/products/2021-valanda-tempranillo"
CLOSED_WINDOW = "/products/2023-closed-window-pinot-noir-willamette-valley"
GOLDEN_CASE = "/products/golden-state-essentials-case"
FESTIVE = "/products/festive-vines-pumpkin-spice-chardonnay-3-pack"
CELEBRATE = "/products/celebrate-the-season-case-1"
KELHAM = "/products/kelham-cabernet-sauvignon-oakville-ava-napa-california-2025"

CREATED = "2026-09-22 00:00:00.000000"

# ---------------------------------------------------------------- honest fixtures
# (steps, answer) — steps are (path, action, params) triples on the recorded URL surface.
HONEST = {
    0: ([("/search", "fill", {"text": "pinot noir", "selector": "input[name=q]"}),
         ("/search?q=pinot+noir&sort_by=price-ascending", "goto", {})],
        'Searching for "pinot noir" and sorting by Price, low to high finds 19 results. '
        "The cheapest bottle is 2023 Rewild Sustainable Pinot Grigio at $13.99; its rating "
        "shows: No reviews yet (0 reviews)."),
    1: ([("/search", "fill", {"text": "moscato", "selector": "input[name=q]"}),
         ("/search?q=moscato&sort_by=price-ascending", "goto", {})],
        'Searching for "moscato" finds 12 products. The cheapest Moscato is 2023 Arenas '
        "Moscato at $10.49. The most expensive one is 2023 Rewild Sustainable Moscato at $19.99."),
    2: ([("/collections/all-wine", "goto", {}),
         ("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon", "goto", {}),
         ("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon&sort_by=price-ascending", "goto", {}),
         (KELHAM, "goto", {})],
        "The Shop All Wine collection filtered to Cabernet Sauvignon and sorted by price low "
        "to high shows 19 wines. The cheapest is 2022 Della Flora Organic Cabernet Sauvignon "
        "at $16.99. The most expensive one comes from the United States."),
    3: ([("/collections/wine-sets-under-50?sort_by=price-ascending", "goto", {}),
         (FESTIVE, "goto", {})],
        "The Wine Sets Under $50 collection lists 31 sets. The cheapest set is Festive Vines "
        "Pumpkin Spice Chardonnay 3-Pack at $33.12, and it contains 3 bottles."),
    4: ([("/collections/all-wine?filter.p.m.drinks.country=Italy&filter.p.m.drinks.sweetness=Sweet", "goto", {})],
        "Filtering Shop All Wine by Country = Italy and Sweetness = Sweet matches 6 wines: "
        "Abbazia Moscato Vino Dolce I.G.T. at $16.99; Abbazia La Tartaruga Moscato Provincia "
        "di Pavia I.G.T. at $12.59; Tesoro Vite Sparkling Moscato at $17.99; Abbazia Moscato "
        "Dolce at $16.99; Tesoro Vite Sparkling Wine Moscato I.G.T. at $15.99; Abbazia "
        "Sparkling Moscato Rosé Dolce at $16.99."),
    5: ([("/collections/sparkling-wine?sort_by=price-ascending", "goto", {})],
        "The Sparkling Wine collection sorted by price low to high lists 14 sparkling wines; "
        "the cheapest is Cinguetto Vino Bianco Frizzante Italy at $12.99."),
    6: ([("/collections/12-bottle-wine-sets?sort_by=price-descending", "goto", {}),
         (CELEBRATE, "goto", {}),
         (CELEBRATE, "click", {"selector": ".pack-option"})],
        "The 12-Bottle Wine Sets collection sorted by price high to low lists 44 sets. The "
        "most expensive is Celebrate the Season Case at $206.30, and the percentage discount "
        "currently shown on it is 19% Off."),
    7: ([(GOLDEN_CASE, "goto", {})],
        "The Golden State Essentials Case contains 6 Bottles In This Case: (1) 2021 Free "
        "Flight Red Blend; (2) 2023 House Party Pinot Grigio; (3) 2022 Redland Ranch Reserve "
        "Zinfandel; (4) 2024 Misirlou Chardonnay; (5) 2024 Wolfson Cellars Sauvignon Blanc; "
        "(6) 2023 Hats & Hides Cabernet Sauvignon Red Lake HIlls. The case split is 3 Red, "
        "3 White, and the 6-pack's per-bottle price is $12.74 per bottle."),
    8: ([("/search", "fill", {"text": "chardonnay reserva", "selector": "input[name=q]"}),
         ("/search?q=chardonnay+reserva", "goto", {}),
         ("/products/2023-ahlma-chardonnay-reserva", "goto", {})],
        "The product with the most customer reviews is 2023 Ahlma Chardonnay Reserva. Its "
        "average rating is 4.6, it has 11 reviews, and 100% of reviewers would recommend it."),
    9: ([("/products/2024-casa-de-alqueria-reserva-red-blend-chile", "goto", {})],
        "The 2024 Casa de Alqueria Reserva Red Blend Chile has won Gold 2026 - Critics "
        "Challenge International Wine Competition. From its Wine Info table: ABV 13.5, "
        "region Valle Central."),
    10: ([("/products/cabs-for-grabs-trio", "goto", {})],
         "The Cabs For Grabs Trio contains 3 Bottles In This Case: (1) 2021 Cremaschi Furlotti "
         "Gran Reserva Cabernet Sauvignon; (2) 2024 Magistrale Cabernet Sauvignon I.G.T. "
         "Veneto; (3) 2023 Fairweather Cabernet Sauvignon. The per-bottle price shown for "
         "the 3-pack is $22.49 per bottle."),
    11: ([("/products/2021-free-flight-pinot-noir", "goto", {}),
          (CLOSED_WINDOW, "goto", {})],
         "Comparing the two: the 2021 Free Flight Pinot Noir has the higher ABV (13.5 vs "
         "12.58). The 2021 Free Flight Pinot Noir holds the award: Silver 2025 - Harvest "
         "Challenge International Wine Competition."),
    12: ([("/products/2022-della-flora-organic-cabernet-sauvignon", "goto", {})],
         "The 2022 Della Flora Organic Cabernet Sauvignon Wine Info rows: Winery Jenna WInes, "
         "Varietal Cabernet Sauvignon, Year 2022, ABV 13.1, Country United States, Region "
         "California."),
    13: ([(TIMETIDE, "fill", {"text": "3", "selector": "[data-qty-input]"}),
          (TIMETIDE, "click", {"selector": "[data-add-to-cart]"}),
          ("/cart", "goto", {})],
         "With 3 bottles of the 2023 Time & Tide Chardonnay Monterey County as a guest, the "
         "cart shows: subtotal $56.97, shipping $14.95, processing $2.95, total $74.87. The "
         'free-shipping progress message reads: "Add 3 bottles for free shipping!"'),
    14: ([("/cart", "goto", {})],
         "Alice's cart holds: 2021 Free Flight Pinot Noir x2 ($29.98); Golden State Essentials "
         "Case x1 ($76.45) — 8 bottles in total, shipping FREE, and the order total is $109.38."),
    15: ([("/cart", "goto", {}),
          ("/checkout/information", "goto", {}),
          ("/checkout/payment", "goto", {}),
          ("/checkout/review", "goto", {}),
          ("/checkout/confirmation/MWS1050", "goto", {})],
         "Checkout complete. The new order number is MWS1050, it ships to San Francisco, CA, "
         "and the order total is $109.38."),
    16: ([(VALANDA, "fill", {"text": "2", "selector": "[data-qty-input]"}),
          (VALANDA, "click", {"selector": "[data-add-to-cart]"}),
          ("/cart", "goto", {}),
          (VALANDA, "click", {"selector": "[data-add-to-cart]"}),
          ("/cart", "goto", {})],
         'With 2 bottles in the cart, the cart says "Minimum 3 Bottles Required for Checkout" '
         "and the Checkout button is disabled (not usable). After adding 1 more bottle of the "
         "2021 Valanda Tempranillo, the cart total is $68.87."),
    17: ([("/", "click", {"selector": "#age-no"})],
         'Clicking "No" on the age gate replaces the page with: "Sorry, you cannot proceed."'),
    18: ([("/", "click", {"selector": "#age-yes"})],
         'Leaving the state dropdown on "Select your state" and clicking "Yes" shows the exact '
         'error: "You must select your state to continue."'),
    19: ([("/", "select", {"selector": "#age-gate select", "value": "UT"}),
          ("/", "click", {"selector": "#age-yes"}),
          (TIMETIDE, "goto", {})],
         'With the Ship-to state set to UT, the 2023 Time & Tide Chardonnay Monterey County '
         'page shows the shipping-restriction message: "Item cannot ship to your state"'),
    20: ([("/account/orders", "goto", {}),
          ("/account/orders/MWS1044", "goto", {})],
         "Bob's most recent order is MWS1044 (September 14, 2026), status Shipped, total "
         "$79.40. It contains: Golden State Essentials Case (6-pack) 1 $76.45."),
    21: ([("/account/orders", "goto", {}),
          ("/account/orders/MWS1048", "goto", {})],
         "David's Processing order is MWS1048, total $95.55. It contains: California Red "
         "Wine Odyssey (red / 6-pack) 1 $92.60."),
    22: ([("/account/orders", "goto", {}),
          ("/account/orders/MWS1043", "goto", {})],
         "Alice's order containing the Oh-So-Sweet Case is MWS1043, status Shipped, total "
         "$91.30, shipped to San Francisco, CA."),
    23: ([("/account/password", "goto", {}),
          ("/account/password", "fill", {"text": "AutumnCellar77!", "selector": "input[name=new_password]"}),
          ("/account/password", "click", {"selector": "button[type=submit]"}),
          ("/account/password", "fill", {"text": "TestPass123!", "selector": "input[name=new_password]"}),
          ("/account/password", "click", {"selector": "button[type=submit]"})],
         'Changing the password to AutumnCellar77! shows: "Password changed successfully."; '
         'changing it back to TestPass123! shows: "Password changed successfully.". The '
         "account page confirms both changes and the original password still signs in."),
    24: ([("/register", "fill", {"text": "honest.run@example.com", "selector": "input[name=email]"}),
          ("/register", "click", {"selector": "button[type=submit]"}),
          (CLOSED_WINDOW, "fill", {"text": "3", "selector": "[data-qty-input]"}),
          (CLOSED_WINDOW, "click", {"selector": "[data-add-to-cart]"}),
          ("/checkout/information", "goto", {}),
          ("/checkout/review", "goto", {}),
          ("/checkout/confirmation/MWS1050", "goto", {})],
         "Registered a new account (honest.run@example.com), added 3 bottles of the 2023 "
         "Closed Window Pinot Noir Willamette Valley, and placed the order. The new order "
         "number is MWS1050 and its total is $77.87."),
    25: ([("/pages/wine-club", "goto", {})],
         "For the Mixed intro case the Wine Club page shows the case price $99.99, processing "
         "fee $2.95, and subtotal $102.94. From the FAQ: the ongoing membership price is "
         "$149.99 plus tax, shipments arrive approximately every 13 weeks, and customer "
         "support is at (855) 966-2224."),
    26: ([("/pages/wine-club", "click", {"selector": "[data-club-tab='reds']"}),
          ("/pages/wine-club", "click", {"selector": "[data-club-tab='whites']"})],
         "The three Wine Club case options: Mixed — 12 unique wines, 1 bottle each; All Reds "
         "— 6 unique red wines, 2 bottles each; All Whites — 6 unique white wines, 2 "
         "bottles each."),
    27: ([("/products/giftcard", "goto", {})],
         "The Gift Cards product page offers selectable amounts of $25, $50, $75 and $100, "
         "and the $100 card is charged at $100.00."),
    28: ([("/blogs/wine-101", "goto", {}),
          ("/blogs/wine-101/how-long-does-wine-last-after-opening", "goto", {})],
         'The Wine 101 article about how long wine lasts after opening is "How Long Does Wine '
         'Last After Opening?". It says most full-bodied reds and whites have an average '
         "shelf life of up to 1-5 days after opening."),
    29: ([("/blogs/wine-101", "goto", {}),
          ("/blogs/wine-101/a-guide-to-wine-storage-temperatures", "goto", {})],
         'The Wine 101 article about wine storage temperatures is "A Guide to Wine Storage '
         'Temperatures". It says the best place for long-term storage is: a wine cellar or '
         "wine storage fridge will be the best for your wine's long-term storage. Two other "
         "factors it lists besides temperature: light exposure, humidity, and bottle "
         "position."),
}

LOGIN_FOR = {14: "alice.j@test.com", 15: "alice.j@test.com", 20: "bob.c@test.com",
              21: "david.k@test.com", 22: "alice.j@test.com", 23: "carol.d@test.com"}

# wrong answers: every fact swapped to a plausible-but-false value
WRONG = {
    0: "The search finds 18 results and the cheapest bottle is 2021 Free Flight Pinot Noir "
       "at $14.99 with 5.0 stars from 1 review.",
    1: "The search finds 13 products; cheapest Abbazia Moscato Dolce $16.99, most expensive "
       "Tesoro Vite Sparkling Moscato $17.99.",
    2: "The filtered list shows 18 wines; cheapest is 2023 Fairweather Cabernet Sauvignon "
       "at $13.99 and the most expensive comes from Chile.",
    3: "The collection lists 30 sets; the cheapest is California Red Wine Odyssey 3-Pack at "
       "$43.17 with 6 bottles.",
    4: "5 wines match: Abbazia Moscato Vino Dolce $16.99 and a few others.",
    5: "The collection lists 15 sparkling wines and the cheapest is Las Falleras Organic "
       "Cava Brut Rosé D.O.P. at $19.99.",
    6: "The most expensive 12-bottle set is Golden State Essentials Case at $76.45 with a "
       "25% discount, out of 45 sets.",
    7: "The case holds 6 bottles, 4 red and 2 white, with a per-bottle price of $11.99.",
    8: "The most-reviewed product is 2024 Redland Ranch Reserve Sauvignon Blanc with 4.2 "
       "stars from 8 reviews and 95% would recommend.",
    9: "It won a Silver medal in 2025 at the Harvest Challenge International Wine "
       "Competition; ABV 12.5, region Napa Valley.",
    10: "The trio contains 3 bottles and the per-bottle price is $20.00.",
    11: "The 2023 Closed Window Pinot Noir has the higher ABV; the Free Flight won a Gold "
        "medal in 2026.",
    12: "Winery Jenna Wines, Varietal Merlot, Year 2021, ABV 14.0, Country Chile, Region "
        "Maipo.",
    13: "Subtotal $55.97, shipping FREE, processing $2.95, total $58.92, and the message "
        "says free shipping unlocked.",
    14: "Alice's cart holds one bottle, shipping $14.95 and the total is $120.00.",
    15: "The new order number is MWS1051, it ships to Seattle, WA, and the total is $79.40.",
    16: 'The cart says "Minimum 6 Bottles Required" and the checkout button works; after '
        "adding one more bottle the total is $70.00.",
    17: "The site shows a welcome message and lets you continue browsing.",
    18: "The gate shows no error and lets you enter.",
    19: "The page shows the wine ships freely to Utah.",
    20: "Bob's most recent order is MWS1045, Delivered, total $104.89, containing the 2022 "
        "Della Flora Organic Cabernet Sauvignon.",
    21: "The Processing order is MWS1049 with the Festive Vines Pumpkin Spice Chardonnay "
        "6-Pack for $65.30.",
    22: "The order is MWS1042, Delivered, total $65.87, shipped to San Francisco, CA.",
    23: "The site rejected the password change with an error message.",
    24: "The new order number is MWS1049 and its total is $59.97.",
    25: "The case price is $149.99, processing $2.95, subtotal $152.94; the FAQ says $99.99 "
        "every 4 weeks and support is (800) 555-0100.",
    26: "Mixed has 6 unique wines 2 bottles each, All Reds has 12 unique wines 1 bottle "
        "each, All Whites has 6 bottles.",
    27: "The only gift card amount is $25, charged at $25.00.",
    28: 'The article "Wine Storage Temperatures" says wine lasts 3-7 days after opening.',
    29: 'The article "How to Store Wine" says the best place is the kitchen fridge, and to '
        "consider temperature and sunlight.",
}


# ---------------------------------------------------------------- DB state builders
def after_stateful(tmp: Path, n: int, initial: Path) -> Path:
    """The compliant after-DB for a stateful task (seed copy + the allowed delta)."""
    after = copy_db(tmp / f"after_{n}.db")
    if n == 13:
        mutate_db(after, [
            ("INSERT INTO cart_items (id, user_id, session_key, variant_id, quantity, "
             "created_at, updated_at) VALUES (9, NULL, 'sess09', 2, 3, ?, ?)", (CREATED, CREATED)),
        ])
    elif n == 16:
        mutate_db(after, [
            ("INSERT INTO cart_items (id, user_id, session_key, variant_id, quantity, "
             "created_at, updated_at) VALUES (9, NULL, 'sess16', 411, 3, ?, ?)", (CREATED, CREATED)),
        ])
    elif n == 15:
        con = sqlite3.connect(after)
        con.execute(
            "INSERT INTO orders (id, order_number, user_id, email, status, ship_to_name, "
            "address_line1, address_line2, city, state, zip_code, phone, payment_label, "
            "subtotal, shipping, processing, total, bottle_count, club_member, created_at, "
            "updated_at) VALUES (9, 'MWS1050', 1, 'alice.j@test.com', 'Processing', "
            "'Alice Johnson', '460 King St', 'Apt 5B', 'San Francisco', 'CA', '94107', "
            "'(415) 555-0165', 'Visa ending in 4242', 106.43, 0.0, 2.95, 109.38, 8, 0, ?, ?)",
            (CREATED, CREATED))
        con.execute(
            "INSERT INTO order_items (id, order_id, variant_id, product_handle, product_title, "
            "variant_title, unit_price, quantity, bottle_count, created_at, updated_at) "
            "VALUES (9, 9, 323, '2021-free-flight-pinot-noir', '2021 Free Flight Pinot Noir', "
            "'Default Title', 14.99, 2, 1, ?, ?)", (CREATED, CREATED))
        con.execute(
            "INSERT INTO order_items (id, order_id, variant_id, product_handle, product_title, "
            "variant_title, unit_price, quantity, bottle_count, created_at, updated_at) "
            "VALUES (10, 9, 403, 'golden-state-essentials-case', 'Golden State Essentials Case', "
            "'6-pack', 76.45, 1, 6, ?, ?)", (CREATED, CREATED))
        con.execute("DELETE FROM cart_items WHERE id IN (1, 2)")
        con.commit(); con.close()
    elif n == 24:
        con = sqlite3.connect(after)
        con.execute(
            "INSERT INTO users (id, email, username, display_name, password_hash, first_name, "
            "last_name, phone, created_at, updated_at) VALUES (5, 'honest.run@example.com', "
            "'honest.run', 'Honest Runner', 'x0123', 'Honest', 'Runner', '', ?, ?)",
            (CREATED, CREATED))
        con.execute(
            "INSERT INTO orders (id, order_number, user_id, email, status, ship_to_name, "
            "address_line1, address_line2, city, state, zip_code, phone, payment_label, "
            "subtotal, shipping, processing, total, bottle_count, club_member, created_at, "
            "updated_at) VALUES (9, 'MWS1050', 5, 'honest.run@example.com', 'Processing', "
            "'Honest Runner', '12 Vine St', '', 'Napa', 'CA', '94558', '', "
            "'Visa ending in 4242', 59.97, 14.95, 2.95, 77.87, 3, 0, ?, ?)",
            (CREATED, CREATED))
        con.execute(
            "INSERT INTO order_items (id, order_id, variant_id, product_handle, product_title, "
            "variant_title, unit_price, quantity, bottle_count, created_at, updated_at) "
            "VALUES (9, 9, 19, '2023-closed-window-pinot-noir-willamette-valley', "
            "'2023 Closed Window Pinot Noir Willamette Valley', 'Default Title', 19.99, 3, 1, "
            "?, ?)", (CREATED, CREATED))
        con.commit(); con.close()
    return after


@pytest.fixture(scope="module")
def seed(tmp_path_factory) -> Path:
    return copy_db(tmp_path_factory.mktemp("seed") / "seed.db")


def _honest_run(root: Path, n: int) -> Path:
    steps, answer = HONEST[n]
    login = LOGIN_FOR.get(n)
    return build_run(root / f"honest_{n}", f"MacysWineShop--{n}", steps, answer, login=login)


def test_honest_pass(seed, tmp_path):
    for n in range(30):
        run_dir = _honest_run(tmp_path, n)
        initial = seed
        if n in STATEFUL:
            after = after_stateful(tmp_path, n, initial)
        else:
            after = seed
        verdict = run_verifier(n, run_dir, initial, after)
        assert verdict.get("pass") is True, f"task {n} honest fixture must PASS: {verdict}"


def test_noop_fails(seed, tmp_path):
    for n in range(30):
        run_dir = noop_run(tmp_path / f"noop_{n}", f"MacysWineShop--{n}")
        verdict = run_verifier(n, run_dir, seed, seed)
        assert verdict.get("pass") is False, f"task {n} no-op must FAIL"
        assert verdict.get("reason") == "final_answer_nonempty"


def test_wrong_answer_fails(seed, tmp_path):
    for n in range(30):
        steps, _ = HONEST[n]
        run_dir = build_run(tmp_path / f"wrong_{n}", f"MacysWineShop--{n}", steps, WRONG[n],
                           login=LOGIN_FOR.get(n))
        if n in STATEFUL:
            after = after_stateful(tmp_path, n, seed)
        else:
            after = seed
        verdict = run_verifier(n, run_dir, seed, after)
        assert verdict.get("pass") is False, f"task {n} wrong answer must FAIL"


def test_shortcut_fails(seed, tmp_path):
    """Correct answer, homepage-only navigation: every task's required surface is beyond
    the homepage, so a memory-recall shortcut must FAIL on the navigation gate."""
    for n in range(30):
        _, answer = HONEST[n]
        run_dir = build_run(tmp_path / f"shortcut_{n}", f"MacysWineShop--{n}", [("/", "click", {})],
                            answer)
        if n in STATEFUL:
            after = after_stateful(tmp_path, n, seed)
        else:
            after = seed
        verdict = run_verifier(n, run_dir, seed, after)
        assert verdict.get("pass") is False, f"task {n} shortcut must FAIL"
        assert "visited" in verdict.get("reason", "") or "required" in verdict.get("reason", "") \
            or "sorted" in verdict.get("reason", "") or "search" in verdict.get("reason", "") \
            or "clicked" in verdict.get("reason", "") or "set_" in verdict.get("reason", "") \
            or "switched" in verdict.get("reason", ""), \
            f"task {n} shortcut must fail on a navigation gate, got {verdict.get('reason')}"


def test_read_only_mutation_fails(seed, tmp_path):
    for n in READ_ONLY:
        steps, answer = HONEST[n]
        run_dir = build_run(tmp_path / f"mut_{n}", f"MacysWineShop--{n}", steps, answer,
                           login=LOGIN_FOR.get(n))
        dirty = copy_db(tmp_path / f"dirty_{n}.db")
        mutate_db(dirty, [("INSERT INTO newsletter_subscribers (id, email, source, created_at, "
                           "updated_at) VALUES (9, 'mutation@example.com', 'footer', ?, ?)",
                           (CREATED, CREATED))])
        verdict = run_verifier(n, run_dir, seed, dirty)
        assert verdict.get("pass") is False, f"read-only task {n} must FAIL on a mutated DB"


def test_stateful_mismatch_fails(seed, tmp_path):
    """Agent self-reports success but the DB is unchanged: stateful tasks must FAIL."""
    for n in STATEFUL:
        steps, answer = HONEST[n]
        run_dir = build_run(tmp_path / f"sm_{n}", f"MacysWineShop--{n}", steps, answer,
                           login=LOGIN_FOR.get(n))
        verdict = run_verifier(n, run_dir, seed, seed)
        assert verdict.get("pass") is False, f"stateful task {n} must FAIL on a state mismatch"


def test_stateful_wrong_delta_fails(seed, tmp_path):
    """A wrong delta (collateral write / wrong row) must FAIL."""
    # T13 with a single-bottle cart row instead of 3 bottles.
    steps, answer = HONEST[13]
    run_dir = build_run(tmp_path / "wd13", "MacysWineShop--13", steps, answer)
    bad = copy_db(tmp_path / "wd13.db")
    mutate_db(bad, [("INSERT INTO cart_items (id, user_id, session_key, variant_id, quantity, "
                     "created_at, updated_at) VALUES (9, NULL, 's', 2, 1, ?, ?)",
                     (CREATED, CREATED))])
    verdict = run_verifier(13, run_dir, seed, bad)
    assert verdict.get("pass") is False

    # T15 with a collateral newsletter row on top of the compliant delta.
    steps, answer = HONEST[15]
    run_dir = build_run(tmp_path / "wd15", "MacysWineShop--15", steps, answer, login="alice")
    bad = after_stateful(tmp_path, 15, seed)
    mutate_db(bad, [("INSERT INTO newsletter_subscribers (id, email, source, created_at, "
                     "updated_at) VALUES (9, 'x@example.com', 'footer', ?, ?)",
                     (CREATED, CREATED))])
    verdict = run_verifier(15, run_dir, seed, bad)
    assert verdict.get("pass") is False

    # T24 with the wrong product in the new order.
    steps, answer = HONEST[24]
    run_dir = build_run(tmp_path / "wd24", "MacysWineShop--24", steps, answer)
    bad = after_stateful(tmp_path, 24, seed)
    mutate_db(bad, [("UPDATE order_items SET product_handle = 'cabs-for-grabs-trio' WHERE id = 9", ())])
    verdict = run_verifier(24, run_dir, seed, bad)
    assert verdict.get("pass") is False


# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fails(seed, tmp_path):
    run_dir = build_run(tmp_path / "tid", "MacysWineShop--0",
                        [("/search?q=pinot+noir&sort_by=price-ascending", "goto", {})],
                        HONEST[0][1])
    verdict = run_verifier(1, run_dir, seed, seed)  # verifier 1 grading task 0's package
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_task_matches"


def test_offsite_url_fails(seed, tmp_path):
    b = RunBuilder(tmp_path / "offsite", "MacysWineShop--0")
    b.step("/", "click", {})
    b.step("https://example.com/pinot", "goto", {})
    b.done(HONEST[0][1])
    run_dir = b.write()
    verdict = run_verifier(0, run_dir, seed, seed)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "all_urls_match_local_origin"


def test_missing_screenshot_fails(seed, tmp_path):
    run_dir = build_run(tmp_path / "noshot", "MacysWineShop--0",
                        [("/search?q=pinot+noir&sort_by=price-ascending", "goto", {})],
                        HONEST[0][1])
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(0, run_dir, seed, seed)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_nondone_trajectory_fails(seed, tmp_path):
    b = RunBuilder(tmp_path / "nondone", "MacysWineShop--0")
    b.step("/search?q=pinot+noir&sort_by=price-ascending", "goto", {})
    b.done(HONEST[0][1])
    run_dir = b.write(terminated=False, reason="max_steps")
    verdict = run_verifier(0, run_dir, seed, seed)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_completed"


def test_tampered_seed_fails(seed, tmp_path):
    """A different initial DB (an extra user) must fail the frozen seed contract."""
    fake = copy_db(tmp_path / "fake_seed.db")
    mutate_db(fake, [("INSERT INTO users (id, email, username, display_name, password_hash, "
                     "first_name, last_name, phone, created_at, updated_at) VALUES "
                     "(5, 'fake@example.com', 'fake', 'Fake', 'x', '', '', '', ?, ?)",
                     (CREATED, CREATED))])
    run_dir = _honest_run(tmp_path, 0)
    verdict = run_verifier(0, run_dir, fake, seed)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "snapshot_contract_invalid"


def test_unavailable_db_fails(tmp_path):
    """Both snapshots missing and the container unreachable: fail closed."""
    run_dir = _honest_run(tmp_path, 0)
    verdict = run_verifier(0, run_dir, tmp_path / "nope1.db", tmp_path / "nope2.db",
                           container="no-such-container")
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "database_unavailable"


def test_trajectory_missing_fails(seed, tmp_path):
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    verdict = run_verifier(0, run_dir, seed, seed)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_unavailable"
