"""Deterministic verifier contract tests for the 16 redesigned macys_wine_shop
deep tasks (PR #196 depth redesign).

Covers, per task: the honest trajectory MUST PASS (fixtures mirror the live
honest walks archived in wh-macys_wine_shop-redesign-evidence/ — the guest and
logged-in checkout chains, the cart-rule chain, the compliance alternative,
the Wine Club comparison, the gift-card minimum discovery, and both KEEP
tasks); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a wrong
answer MUST FAIL; a shortcut (correct answer, homepage-only navigation) MUST
FAIL for every task (all 16 required surfaces reach beyond the homepage).
Read-only task 14 MUST FAIL on a mutated after-DB. Every stateful task MUST
FAIL on a state mismatch (claimed success, unchanged DB); selected tasks MUST
FAIL on wrong-state deltas (wrong product, wrong ship state, wrong quantity).
Package tampering (task_id mismatch, off-site URLs, missing screenshots,
non-done trajectory, tampered seed, unavailable DB) MUST fail closed.

No docker, no LLM: snapshots are seed copies mutated through sqlite (the exact
allowed after-state per task), trajectories are hand-written in the
agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, SEED_DB, RunBuilder, _acquire_seed, address_statements,  # noqa: E402
                      copy_db, delete_cart_statements, mutate_db, noop_run,
                      order_statements, run_verifier, user_statements)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file() and not _acquire_seed().is_file(),
                               reason="seed DB unavailable")

ALL_TASKS = list(range(16))
STATEFUL = [n for n in ALL_TASKS if n != 14]
GUEST_EMAIL = "mws.redesign@example.com"
GUEST_SHIP = {"name": "Morgan Cellar", "line1": "77 Vine Street", "city": "Napa",
              "state": "CA", "zip": "94558"}
GUEST_PAY = "Visa ending in 4242"
CAROL = "carol.d@test.com"
BOB = "bob.c@test.com"
DAVID = "david.k@test.com"
PASSWORD = "TestPass123!"

DELLA = {"variant_id": 394, "handle": "2022-della-flora-organic-cabernet-sauvignon",
         "title": "2022 Della Flora Organic Cabernet Sauvignon",
         "variant_title": "Default Title", "unit_price": 16.99, "quantity": 3, "bottle_count": 1}
CREMASCHI = {"variant_id": 261, "handle": "2021-cremaschi-furlotti-gran-reserva-cabernet-sauvignon",
             "title": "2021 Cremaschi Furlotti Gran Reserva Cabernet Sauvignon",
             "variant_title": "Default Title", "unit_price": 17.49, "quantity": 3, "bottle_count": 1}
TIMETIDE = {"variant_id": 2, "handle": "2023-time-tide-chardonnay-monterey-county",
            "title": "2023 Time & Tide Chardonnay Monterey County",
            "variant_title": "Default Title", "unit_price": 18.99, "quantity": 3, "bottle_count": 1}
VALDEMACUCO = {"variant_id": 304, "handle": "2023-valdemacuco-tempranillo",
               "title": "2023 Valdemacuco Tempranillo", "variant_title": "Default Title",
               "unit_price": 13.29, "quantity": 3, "bottle_count": 1}
CASE12 = {"variant_id": 404, "handle": "golden-state-essentials-case",
          "title": "Golden State Essentials Case", "variant_title": "12-pack",
          "unit_price": 143.90, "quantity": 1, "bottle_count": 12}
CHIANTI = {"variant_id": 289, "handle": "2021-beni-duilio-castellani-riserva-chianti-docg",
           "title": "2021 Beni Duilio Castellani Riserva Chianti DOCG",
           "variant_title": "Default Title", "unit_price": 22.99, "quantity": 3, "bottle_count": 1}
TRIO = {"variant_id": 410, "handle": "cabs-for-grabs-trio", "title": "Cabs For Grabs Trio",
        "variant_title": "3-pack", "unit_price": 67.47, "quantity": 1, "bottle_count": 3}
VALANDA5 = {"variant_id": 411, "handle": "2021-valanda-tempranillo",
            "title": "2021 Valanda Tempranillo", "variant_title": "Default Title",
            "unit_price": 16.99, "quantity": 5, "bottle_count": 1}
CLOSED2 = {"variant_id": 19, "handle": "2023-closed-window-pinot-noir-willamette-valley",
           "title": "2023 Closed Window Pinot Noir Willamette Valley",
           "variant_title": "Default Title", "unit_price": 19.99, "quantity": 2, "bottle_count": 1}
MARTHAS = {"variant_id": 59, "handle": "marthas-chardonnay-collection",
           "title": "Martha's Chardonnay Collection", "variant_title": "white / 6-pack",
           "unit_price": 86.65, "quantity": 1, "bottle_count": 6}
ODYSSEY = {"variant_id": 359, "handle": "california-red-wine-odyssey",
           "title": "California Red Wine Odyssey", "variant_title": "red / 6-pack",
           "unit_price": 92.60, "quantity": 1, "bottle_count": 6}
GC100 = {"variant_id": 415, "handle": "giftcard", "title": "Macy's Wine Shop Gift card",
         "variant_title": "100", "unit_price": 100.00, "quantity": 1, "bottle_count": 1}
CINGUETTO2 = {"variant_id": 92, "handle": "cinguetto-vino-bianco-frizzante-italy",
              "title": "Cinguetto Vino Bianco Frizzante Italy",
              "variant_title": "Default Title", "unit_price": 12.99, "quantity": 2, "bottle_count": 1}
MERLOT3 = {"variant_id": 68, "handle": "cellar-select-merlot-3-pack",
           "title": "Cellar Select: Merlot 3-Pack", "variant_title": "red / 3-pack",
           "unit_price": 44.07, "quantity": 1, "bottle_count": 3}
ZINFANDEL = {"variant_id": 156, "handle": "2023-redland-ranch-reserve-zinfandel",
             "title": "2022 Redland Ranch Reserve Zinfandel", "variant_title": "Default Title",
             "unit_price": 15.99, "quantity": 3, "bottle_count": 1}
MOSCATO6 = {"variant_id": 263, "handle": "2024-house-party-moscato",
            "title": "2024 House Party Moscato", "variant_title": "Default Title",
            "unit_price": 11.89, "quantity": 6, "bottle_count": 1}
AHLMA3 = {"variant_id": 256, "handle": "2023-ahlma-chardonnay-reserva",
          "title": "2023 Ahlma Chardonnay Reserva", "variant_title": "Default Title",
          "unit_price": 13.29, "quantity": 3, "bottle_count": 1}
CLOSED3 = {"variant_id": 19, "handle": "2023-closed-window-pinot-noir-willamette-valley",
           "title": "2023 Closed Window Pinot Noir Willamette Valley",
           "variant_title": "Default Title", "unit_price": 19.99, "quantity": 3, "bottle_count": 1}


# ------------------------------------------------------------------ honest answers
def honest_answer(n: int) -> str:
    return {
        0: ("The two cheapest Cabernet Sauvignons are the 2022 Della Flora Organic "
            "Cabernet Sauvignon at $16.99 (rated 4.2 with 6 reviews) and the 2021 "
            "Cremaschi Furlotti Gran Reserva Cabernet Sauvignon at $17.49 (rated 4.6 "
            "with 8 reviews). I bought the cheaper one, the Della Flora: 3 bottles. "
            "Order MWS1050 is confirmed with a total of $68.87 (subtotal $50.97, "
            "shipping $14.95, processing $2.95)."),
        1: ("Bought 3 bottles of the 2023 Time & Tide Chardonnay Monterey County as a "
            "guest. Order MWS1050 is confirmed: total $74.87 (subtotal $56.97, shipping "
            "$14.95, processing $2.95). Shipping was not free — with only 3 bottles the "
            "cart said to add 3 more bottles for free shipping, and checkout charged "
            "$14.95 for shipping."),
        2: ("Filtering Shop All Wine to Color = Red and Country = Spain leaves 11 wines. "
            "The highest customer rating among them is 5.0 stars: the 2023 Valdemacuco "
            "Tempranillo at $13.29 — its page confirms 5.0 out of 5 with 1 review and "
            "100% would recommend, region Rioja, ABV 13.5%. I bought 3 bottles: order "
            "MWS1050, total $57.77 (subtotal $39.87, shipping $14.95, processing $2.95)."),
        3: ("Golden State Essentials Case: the 6-pack costs $76.45, which is $12.74 per "
            "bottle; the 12-pack costs $143.90, which is $11.99 per bottle. The 12-pack "
            "has the lower per-bottle price, so I bought it. The case contains 12 bottles "
            "(6 Red, 6 White): 2021 Free Flight Red Blend, 2023 House Party Pinot Grigio, "
            "2022 Redland Ranch Reserve Zinfandel, 2024 Misirlou Chardonnay, 2024 Wolfson "
            "Cellars Sauvignon Blanc, and 2023 Hats & Hides Cabernet Sauvignon. Order "
            "MWS1050 total: $146.85 (subtotal $143.90, shipping FREE with 12 bottles, "
            "processing $2.95)."),
        4: ("With my shipping state set to Utah, the 2023 Time & Tide Pinot Noir "
            "Monterey County page shows 'Item cannot ship to your state' instead of an "
            "Add to Cart button. In the Red Wines collection almost every card is blocked "
            "the same way; the 2021 Beni Duilio Castellani Riserva Chianti DOCG ($22.99) "
            "is the red the site can ship to Utah. I bought 3 bottles shipped to Salt "
            "Lake City, UT: order MWS1050, total $86.87 (subtotal $68.97, shipping "
            "$14.95, processing $2.95)."),
        5: ("My saved address on file is in Seattle, WA (1201 3rd Ave, Unit 19) and my "
            "saved card is the Visa ending in 1881. I added 2 more bottles of the 2021 "
            "Valanda Tempranillo to the cart (joining the Cabs For Grabs Trio and the 3 "
            "Tempranillo bottles already there) and checked out with the saved details. "
            "Order MWS1050: total $155.37 (subtotal $152.42, shipping FREE with 8 "
            "bottles, processing $2.95)."),
        6: ("I added a second address to my account (Kayla Davis, 118 Larimer St, Apt 4, "
            "Denver, CO 80204) and checked my cart out shipping to it, paying with a new "
            "Mastercard ending in 2222. The order (2 bottles of the 2023 Closed Window "
            "Pinot Noir Willamette Valley plus the Martha's Chardonnay Collection 6-pack, "
            "8 bottles total) is confirmed as MWS1050 with total $129.58 (subtotal "
            "$126.63, shipping FREE, processing $2.95)."),
        7: ("With 2 bottles in the cart the cart page shows 'Minimum 3 Bottles Required "
            "for Checkout' with the Checkout button disabled, and the summary says 'Add 4 "
            "bottles for free shipping!'. After raising the quantity to 3 the checkout "
            "unlocked (shipping $14.95, 'Add 3 bottles for free shipping!'); at 6 bottles "
            "the note switched to 'Free Shipping unlocked!' and shipping became FREE. I "
            "placed the order for 6 bottles of the 2021 Valanda Tempranillo: order "
            "MWS1050, total $104.89 (subtotal $101.94, shipping FREE, processing $2.95)."),
        8: ("The order still Processing is MWS1048 — the California Red Wine Odyssey "
            "(red / 6-pack) at $92.60, total $95.55. I cleared the other items from my "
            "cart and reordered exactly that six-pack. The new order is MWS1050 with the "
            "same total $95.55 (subtotal $92.60, shipping FREE with 6 bottles, "
            "processing $2.95)."),
        9: ("With the $100.00 gift card and one sparkling bottle the cart showed 'Minimum 3 "
            "Bottles Required for Checkout' with checkout disabled — so the gift card "
            "DOES count toward the 3-bottle minimum (2 items = 2 bottles). Adding a "
            "second sparkling bottle reached 3 bottles and unlocked checkout (shipping "
            "$14.95, 'Add 3 bottles for free shipping!'). Order MWS1050: the $100 gift "
            "card plus 2 bottles of Cinguetto Vino Bianco Frizzante Italy ($12.99 each), "
            "total $143.88 (subtotal $125.98, shipping $14.95, processing $2.95)."),
        10: ("Wine Club cases: the Mixed intro case includes 12 unique wines, 1 bottle "
             "each; All Reds includes 6 unique red wines, 2 bottles each; All Whites "
             "includes 6 unique white wines, 2 bottles each. Each 12-bottle intro case is "
             "$99.99 with free shipping (plus $2.95 processing). Per the FAQ, membership "
             "renews quarterly at $149.99, shipments arrive approximately every 13 weeks, "
             "and Customer Support is at (855) 966-2224. Since we drink reds only, I also "
             "ordered the Cellar Select: Merlot 3-Pack ($44.07) as a first taste: order "
             "MWS1050, total $61.97 (subtotal $44.07, shipping $14.95, processing $2.95)."),
        11: ("The Wine 101 storage guide says the best overall storage temperature is "
             "around 55 degrees Fahrenheit, with humidity ideally between 60-68% to keep "
             "corks from drying out, bottles laid on their side, and away from sunlight — "
             "a regular kitchen fridge is too cold for wine. It names full-bodied reds "
             "like Cabernet Sauvignon, Malbec, and Zinfandel as the keepers for long-term "
             "storage. Following that, I bought 3 bottles of the 2022 Redland Ranch "
             "Reserve Zinfandel ($15.99): order MWS1050, total $65.87 (subtotal $47.97, "
             "shipping $14.95, processing $2.95)."),
        12: ("2024 House Party Moscato ($11.89): Gold, 2026 Critics Challenge "
             "International Wine Competition, ABV 11.0%. 2024 Misirlou Chardonnay "
             "($13.99): Gold, 2025 Harvest Challenge International Wine Competition, ABV "
             "13.5%. The Moscato is cheaper, so I bought 6 bottles — the cart unlocked "
             "free shipping at 6 bottles ('Free Shipping unlocked!'). Order MWS1050, "
             "total $74.29 (subtotal $71.34, shipping FREE, processing $2.95)."),
        13: ("Searching 'chardonnay', the wine with the most customer reviews is the 2023 "
             "Ahlma Chardonnay Reserva with 11 reviews — the most on the site among "
             "chardonnays. Its page shows 4.6 out of 5 stars and 100% would recommend it. "
             "I bought 3 bottles at $13.29 each: order MWS1050, total $57.77 (subtotal "
             "$39.87, shipping $14.95, processing $2.95)."),
        14: ("The account page confirmed both password changes with 'Password changed "
             "successfully.' — first to AutumnCellar77!, then back to TestPass123!. After "
             "signing out, signing back in with the original password TestPass123! works."),
        15: ("I registered a brand-new account (mws.redesign.r0815@example.com), added 3 "
             "bottles of the 2023 Closed Window Pinot Noir Willamette Valley ($19.99 "
             "each), and placed the order with my own details. The new order is MWS1050 "
             "with a total of $77.87 (subtotal $59.97, shipping $14.95, processing "
             "$2.95)."),
    }[n]


# ------------------------------------------------------------------ honest trajectories
def _checkout_steps(b, ship_state="CA"):
    b.step("/checkout/information", "fill", {"text": GUEST_EMAIL, "selector": "input[name=email]"})
    b.step("/checkout/information", "fill", {"text": "Morgan Cellar", "selector": "input[name=ship_to_name]"})
    b.step("/checkout/information", "fill", {"text": "77 Vine Street", "selector": "input[name=address_line1]"})
    b.step("/checkout/information", "fill", {"text": "Napa", "selector": "input[name=city]"})
    b.step("/checkout/information", "select", {"value": ship_state, "selector": "select[name=state]"})
    b.step("/checkout/information", "fill", {"text": "94558", "selector": "input[name=zip_code]"})
    b.step("/checkout/information", "click", {"selector": "button[type=submit]"},
           url_after="/checkout/payment")
    b.step("/checkout/payment", "fill", {"text": "4242424242424242", "selector": "input[name=card_number]"})
    b.step("/checkout/payment", "fill", {"text": "Morgan Cellar", "selector": "input[name=card_holder]"})
    b.step("/checkout/payment", "select", {"value": "09", "selector": "select[name=exp_month]"})
    b.step("/checkout/payment", "select", {"value": "2029", "selector": "select[name=exp_year]"})
    b.step("/checkout/payment", "fill", {"text": "321", "selector": "input[name=card_cvc]"})
    b.step("/checkout/payment", "click", {"selector": "button[type=submit]"},
           url_after="/checkout/review")
    b.step("/checkout/review", "check", {"selector": "input[name=age_confirmed]"})
    b.step("/checkout/review", "click", {"selector": "button[type=submit]"},
           url_after="/checkout/confirmation/MWS1050")
    b.step("/checkout/confirmation/MWS1050", "goto", {})
    return b


def honest_run(root: Path, n: int) -> Path:
    b = RunBuilder(root, f"MacysWineShop--{n}")
    if n == 0:
        b.step("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon"
               "&sort_by=price-ascending", "goto", {})
        b.step("/products/2022-della-flora-organic-cabernet-sauvignon", "goto", {})
        b.step("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon"
               "&sort_by=price-ascending", "goto", {})
        b.step("/products/2021-cremaschi-furlotti-gran-reserva-cabernet-sauvignon", "goto", {})
        b.step("/collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon"
               "&sort_by=price-ascending", "goto", {})
        b.step("/products/2022-della-flora-organic-cabernet-sauvignon", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2022-della-flora-organic-cabernet-sauvignon", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 1:
        b.step("/search?q=time+tide+chardonnay", "goto", {})
        b.step("/products/2023-time-tide-chardonnay-monterey-county", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2023-time-tide-chardonnay-monterey-county", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 2:
        b.step("/collections/all-wine", "goto", {})
        b.step("/collections/all-wine?filter.p.m.drinks.color=Red", "goto", {})
        b.step("/collections/all-wine?filter.p.m.drinks.color=Red&filter.p.m.drinks.country=Spain",
               "goto", {})
        b.step("/products/2023-valdemacuco-tempranillo", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2023-valdemacuco-tempranillo", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 3:
        b.step("/search?q=golden+state+essentials", "goto", {})
        b.step("/products/golden-state-essentials-case", "click",
               {"selector": "[data-pack-option]:has-text('12 Pack')"})
        b.step("/products/golden-state-essentials-case", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 4:
        b.step("/search?q=time+tide+pinot+noir", "goto", {})
        b.step("/products/2023-time-tide-pinot-noir-monterey-county", "goto", {})
        b.step("/collections/red-wine", "goto", {})
        b.step("/products/2021-beni-duilio-castellani-riserva-chianti-docg", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2021-beni-duilio-castellani-riserva-chianti-docg", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b, ship_state="UT")
    elif n == 5:
        b.login(BOB)
        b.step("/account/addresses", "goto", {})
        b.step("/account/payment", "goto", {})
        b.step("/search?q=valanda", "goto", {})
        b.step("/products/2021-valanda-tempranillo", "fill",
               {"text": "2", "selector": "[data-qty-input]"})
        b.step("/products/2021-valanda-tempranillo", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        b.step("/checkout/information", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/payment")
        b.step("/checkout/payment", "select", {"value": "3", "selector": "select#payment_id"},
               )
        b.step("/checkout/review", "check", {"selector": "input[name=age_confirmed]"})
        b.step("/checkout/review", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/confirmation/MWS1050")
        b.step("/checkout/confirmation/MWS1050", "goto", {})
    elif n == 6:
        b.login(CAROL)
        b.step("/account/addresses", "fill", {"text": "Kayla Davis", "selector": "#full_name"})
        b.step("/account/addresses", "fill", {"text": "118 Larimer St", "selector": "#line1"})
        b.step("/account/addresses", "fill", {"text": "Apt 4", "selector": "#line2"})
        b.step("/account/addresses", "fill", {"text": "Denver", "selector": "#city"})
        b.step("/account/addresses", "select", {"value": "CO", "selector": "#state"})
        b.step("/account/addresses", "fill", {"text": "80204", "selector": "#zip_code"})
        b.step("/account/addresses", "fill", {"text": "(303) 555-0148", "selector": "#phone"})
        b.step("/account/addresses", "click", {"selector": "button[type=submit]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        b.step("/checkout/information", "select", {"value": "6", "selector": "select#address_id"},
               )
        b.step("/checkout/payment", "fill", {"text": "5555444433332222",
                                             "selector": "input[name=card_number]"})
        b.step("/checkout/payment", "fill", {"text": "Carol Davis", "selector": "input[name=card_holder]"})
        b.step("/checkout/payment", "select", {"value": "08", "selector": "select[name=exp_month]"})
        b.step("/checkout/payment", "select", {"value": "2028", "selector": "select[name=exp_year]"})
        b.step("/checkout/payment", "fill", {"text": "456", "selector": "input[name=card_cvc]"})
        b.step("/checkout/payment", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/review")
        b.step("/checkout/review", "check", {"selector": "input[name=age_confirmed]"})
        b.step("/checkout/review", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/confirmation/MWS1050")
        b.step("/checkout/confirmation/MWS1050", "goto", {})
    elif n == 7:
        b.step("/search?q=valanda", "goto", {})
        b.step("/products/2021-valanda-tempranillo", "fill",
               {"text": "2", "selector": "[data-qty-input]"})
        b.step("/products/2021-valanda-tempranillo", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "fill", {"text": "3", "selector": ".cart-qty input[name=quantity]"})
        b.step("/cart", "click", {"selector": "button[aria-label=Update]"})
        b.step("/cart", "click", {"selector": "button[aria-label=Increase]"})
        b.step("/cart", "click", {"selector": "button[aria-label=Increase]"})
        b.step("/cart", "click", {"selector": "button[aria-label=Increase]"})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 8:
        b.login(DAVID)
        b.step("/account/orders", "goto", {})
        b.step("/account/orders/MWS1048", "goto", {})
        b.step("/search?q=california+wine+odyssey", "goto", {})
        b.step("/products/california-red-wine-odyssey", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": "form[action^='/cart/remove/7'] button"})
        b.step("/cart", "click", {"selector": "form[action^='/cart/remove/8'] button"})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        b.step("/checkout/information", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/payment")
        b.step("/checkout/payment", "select", {"value": "5", "selector": "select#payment_id"})
        b.step("/checkout/review", "check", {"selector": "input[name=age_confirmed]"})
        b.step("/checkout/review", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/confirmation/MWS1050")
        b.step("/checkout/confirmation/MWS1050", "goto", {})
    elif n == 9:
        b.step("/products/giftcard", "select", {"value": "415", "selector": "#variant-select"})
        b.step("/products/giftcard", "click", {"selector": "[data-add-to-cart]"})
        b.step("/collections/sparkling-wine", "goto", {})
        b.step("/products/cinguetto-vino-bianco-frizzante-italy", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "fill", {"text": "2", "selector": ".cart-qty input[name=quantity]"})
        b.step("/cart", "click", {"selector": "button[aria-label=Update]"})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 10:
        b.step("/pages/wine-club", "click", {"selector": "button[data-club-tab=reds]"})
        b.step("/pages/wine-club", "click", {"selector": "button[data-club-tab=mixed]"})
        b.step("/pages/wine-club", "click", {"selector": "button[data-club-tab=whites]"})
        b.step("/pages/wine-club", "click", {"selector": "details.faq-item summary"})
        b.step("/search?q=cellar+select+merlot", "goto", {})
        b.step("/products/cellar-select-merlot-3-pack", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 11:
        b.step("/blogs/wine-101", "goto", {})
        b.step("/blogs/wine-101/a-guide-to-wine-storage-temperatures", "goto", {})
        b.step("/search?q=zinfandel", "goto", {})
        b.step("/products/2023-redland-ranch-reserve-zinfandel", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2023-redland-ranch-reserve-zinfandel", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 12:
        b.step("/search?q=house+party+moscato", "goto", {})
        b.step("/products/2024-house-party-moscato", "goto", {})
        b.step("/search?q=misirlou+chardonnay", "goto", {})
        b.step("/products/2024-misirlou-chardonnay", "goto", {})
        b.step("/search?q=house+party+moscato", "goto", {})
        b.step("/products/2024-house-party-moscato", "fill",
               {"text": "6", "selector": "[data-qty-input]"})
        b.step("/products/2024-house-party-moscato", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 13:
        b.step("/search?q=chardonnay", "goto", {})
        b.step("/products/2023-ahlma-chardonnay-reserva", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2023-ahlma-chardonnay-reserva", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        _checkout_steps(b)
    elif n == 14:
        b.login(CAROL)
        b.step("/account/password", "fill",
               {"text": PASSWORD, "selector": "input[name=current_password]"})
        b.step("/account/password", "fill",
               {"text": "AutumnCellar77!", "selector": "input[name=new_password]"})
        b.step("/account/password", "fill",
               {"text": "AutumnCellar77!", "selector": "input[name=confirm_password]"})
        b.step("/account/password", "click", {"selector": "button[type=submit]"})
        b.step("/account/password", "fill",
               {"text": "AutumnCellar77!", "selector": "input[name=current_password]"})
        b.step("/account/password", "fill",
               {"text": PASSWORD, "selector": "input[name=new_password]"})
        b.step("/account/password", "fill",
               {"text": PASSWORD, "selector": "input[name=confirm_password]"})
        b.step("/account/password", "click", {"selector": "button[type=submit]"})
        b.step("/account", "goto", {})
        b.step("/account", "click", {"selector": "form[action='/logout'] button"},
               url_after="/")
        b.step("/login", "fill", {"text": CAROL, "selector": "input[name=email]"})
        b.step("/login", "fill", {"text": PASSWORD, "selector": "input[name=password]"})
        b.step("/login", "click", {"selector": "button[type=submit]"}, url_after="/account")
    elif n == 15:
        b.step("/register", "fill", {"text": "mws.redesign.r0815@example.com",
                                     "selector": "input[name=email]"})
        b.step("/register", "fill", {"text": "Morgan", "selector": "input[name=first_name]"})
        b.step("/register", "fill", {"text": "Cellar", "selector": "input[name=last_name]"})
        b.step("/register", "fill", {"text": "CellarDoor88!", "selector": "input[name=password]"})
        b.step("/register", "fill", {"text": "CellarDoor88!", "selector": "input[name=confirm]"})
        b.step("/register", "click", {"selector": "button[type=submit]"}, url_after="/account")
        b.step("/search?q=closed+window+pinot+noir", "goto", {})
        b.step("/products/2023-closed-window-pinot-noir-willamette-valley", "fill",
               {"text": "3", "selector": "[data-qty-input]"})
        b.step("/products/2023-closed-window-pinot-noir-willamette-valley", "click",
               {"selector": "[data-add-to-cart]"})
        b.step("/cart", "goto", {})
        b.step("/cart", "click", {"selector": ".cart-side a.btn-primary"},
               url_after="/checkout/information")
        b.step("/checkout/information", "fill",
               {"text": "mws.redesign.r0815@example.com", "selector": "input[name=email]"})
        b.step("/checkout/information", "fill", {"text": "Morgan Cellar",
                                                 "selector": "input[name=ship_to_name]"})
        b.step("/checkout/information", "fill", {"text": "77 Vine Street",
                                                 "selector": "input[name=address_line1]"})
        b.step("/checkout/information", "fill", {"text": "Napa", "selector": "input[name=city]"})
        b.step("/checkout/information", "select", {"value": "CA", "selector": "select[name=state]"})
        b.step("/checkout/information", "fill", {"text": "94558", "selector": "input[name=zip_code]"})
        b.step("/checkout/information", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/payment")
        b.step("/checkout/payment", "fill", {"text": "4242424242424242",
                                             "selector": "input[name=card_number]"})
        b.step("/checkout/payment", "fill", {"text": "Morgan Cellar",
                                             "selector": "input[name=card_holder]"})
        b.step("/checkout/payment", "select", {"value": "09", "selector": "select[name=exp_month]"})
        b.step("/checkout/payment", "select", {"value": "2029", "selector": "select[name=exp_year]"})
        b.step("/checkout/payment", "fill", {"text": "321", "selector": "input[name=card_cvc]"})
        b.step("/checkout/payment", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/review")
        b.step("/checkout/review", "check", {"selector": "input[name=age_confirmed]"})
        b.step("/checkout/review", "click", {"selector": "button[type=submit]"},
               url_after="/checkout/confirmation/MWS1050")
        b.step("/checkout/confirmation/MWS1050", "goto", {})
    b.done(honest_answer(n))
    return b.write()


# ------------------------------------------------------------------ after-state mutators
def stateful_after_db(n: int, target: Path) -> Path:
    """Materialize the exact allowed after-state for task n on a seed copy."""
    if n == 0:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 50.97, 14.95, 68.87, 3, [DELLA])
    elif n == 1:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 56.97, 14.95, 74.87, 3, [TIMETIDE])
    elif n == 2:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 39.87, 14.95, 57.77, 3, [VALDEMACUCO])
    elif n == 3:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 143.90, 0.0, 146.85, 12, [CASE12])
    elif n == 4:
        ut_ship = {"name": "Utah Cellar", "line1": "350 S 400 W", "city": "Salt Lake City",
                   "state": "UT", "zip": "84101"}
        stmts = order_statements("MWS1050", None, "utah.cellar@example.com", ut_ship,
                                 GUEST_PAY, 68.97, 14.95, 86.87, 3, [CHIANTI])
    elif n == 5:
        bob_ship = {"name": "Bob Chen", "line1": "1201 3rd Ave", "line2": "Unit 19",
                    "city": "Seattle", "state": "WA", "zip": "98101"}
        stmts = (order_statements("MWS1050", 2, BOB, bob_ship, "Visa ending in 1881",
                                  152.42, 0.0, 155.37, 8, [TRIO, VALANDA5])
                 + delete_cart_statements([3, 4]))
    elif n == 6:
        denver = {"name": "Kayla Davis", "line1": "118 Larimer St", "line2": "Apt 4",
                  "city": "Denver", "state": "CO", "zip": "80204", "phone": "(303) 555-0148"}
        stmts = (address_statements(3, "Kayla Davis", "118 Larimer St", "Apt 4", "Denver",
                                    "CO", "80204", "(303) 555-0148")
                 + order_statements("MWS1050", 3, CAROL, denver, "Mastercard ending in 2222",
                                    126.63, 0.0, 129.58, 8, [CLOSED2, MARTHAS])
                 + delete_cart_statements([5, 6]))
    elif n == 7:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 101.94, 0.0, 104.89, 6,
                                 [{**VALANDA5, "quantity": 6}])
    elif n == 8:
        ny_ship = {"name": "David Kim", "line1": "350 5th Ave", "line2": "Floor 22",
                   "city": "New York", "state": "NY", "zip": "10118"}
        stmts = (order_statements("MWS1050", 4, DAVID, ny_ship, "Visa ending in 7321",
                                  92.60, 0.0, 95.55, 6, [ODYSSEY])
                 + delete_cart_statements([7, 8]))
    elif n == 9:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 125.98, 14.95, 143.88, 3, [GC100, CINGUETTO2])
    elif n == 10:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 44.07, 14.95, 61.97, 3, [MERLOT3])
    elif n == 11:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 47.97, 14.95, 65.87, 3, [ZINFANDEL])
    elif n == 12:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 71.34, 0.0, 74.29, 6, [MOSCATO6])
    elif n == 13:
        stmts = order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                 39.87, 14.95, 57.77, 3, [AHLMA3])
    elif n == 15:
        stmts = (user_statements("mws.redesign.r0815@example.com", "Morgan", "Cellar")
                 + order_statements("MWS1050", 5, "mws.redesign.r0815@example.com",
                                    GUEST_SHIP, GUEST_PAY, 59.97, 14.95, 77.87, 3, [CLOSED3]))
    else:
        raise ValueError(n)
    return mutate_db(copy_db(target), stmts)


# ------------------------------------------------------------------ honest PASS
@pytest.mark.parametrize("n", ALL_TASKS)
def test_honest_pass(tmp_path, n):
    run_dir = honest_run(tmp_path / f"h{n}", n)
    initial = copy_db(tmp_path / f"init{n}.db")
    after = stateful_after_db(n, tmp_path / f"after{n}.db") if n in STATEFUL else copy_db(
        tmp_path / f"after{n}.db")
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)


# ------------------------------------------------------------------ no-op FAIL
@pytest.mark.parametrize("n", ALL_TASKS)
def test_noop_fail(tmp_path, n):
    run_dir = noop_run(tmp_path / f"noop{n}", f"MacysWineShop--{n}")
    initial = copy_db(tmp_path / f"init{n}.db")
    after = copy_db(tmp_path / f"after{n}.db")
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "final_answer_nonempty"


# ------------------------------------------------------------------ wrong answer FAIL
WRONG_ANSWERS = {n: "I looked around but could not find anything relevant to report." 
                for n in ALL_TASKS}

@pytest.mark.parametrize("n", ALL_TASKS)
def test_wrong_answer_fail(tmp_path, n):
    run_dir = honest_run(tmp_path / f"w{n}", n)
    traj_file = run_dir / "trajectory.json"
    traj = json.loads(traj_file.read_text())
    traj["final_answer"] = WRONG_ANSWERS[n]
    traj_file.write_text(json.dumps(traj))
    initial = copy_db(tmp_path / f"init{n}.db")
    after = stateful_after_db(n, tmp_path / f"after{n}.db") if n in STATEFUL else copy_db(
        tmp_path / f"after{n}.db")
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] != "final_answer_nonempty"  # the answer gates come later


# ------------------------------------------------------------------ shortcut FAIL
@pytest.mark.parametrize("n", ALL_TASKS)
def test_homepage_shortcut_fail(tmp_path, n):
    b = RunBuilder(tmp_path / f"s{n}", f"MacysWineShop--{n}")
    b.step("/", "click", {"selector": "body"})
    b.done(honest_answer(n))
    run_dir = b.write()
    initial = copy_db(tmp_path / f"init{n}.db")
    after = stateful_after_db(n, tmp_path / f"after{n}.db") if n in STATEFUL else copy_db(
        tmp_path / f"after{n}.db")
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False


# ------------------------------------------------------------------ read-only tamper FAIL
def test_readonly_task_mutated_after_db_fail(tmp_path):
    n = 14
    run_dir = honest_run(tmp_path / f"ro{n}", n)
    initial = copy_db(tmp_path / "init.db")
    after = mutate_db(copy_db(tmp_path / "after.db"),
                      [("UPDATE users SET phone = '(312) 555-0000' WHERE id = 3", ())])
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "read_only_db_unchanged"


# ------------------------------------------------------------------ state mismatch FAIL
@pytest.mark.parametrize("n", STATEFUL)
def test_state_mismatch_fail(tmp_path, n):
    run_dir = honest_run(tmp_path / f"m{n}", n)
    initial = copy_db(tmp_path / f"init{n}.db")
    after = copy_db(tmp_path / f"after{n}.db")  # unchanged seed: no order landed
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False


# ------------------------------------------------------------------ wrong-state FAIL
def test_wrong_product_delta_fail(tmp_path):
    n = 0
    run_dir = honest_run(tmp_path / f"wp{n}", n)
    initial = copy_db(tmp_path / "init.db")
    after = mutate_db(copy_db(tmp_path / "after.db"),
                      order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                       52.47, 14.95, 68.87, 3, [CREMASCHI]))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "db_order_item_della_flora"


def test_wrong_ship_state_delta_fail(tmp_path):
    n = 4
    run_dir = honest_run(tmp_path / f"ws{n}", n)
    initial = copy_db(tmp_path / "init.db")
    ca_ship = {"name": "Utah Cellar", "line1": "350 S 400 W", "city": "Sacramento",
               "state": "CA", "zip": "94203"}
    after = mutate_db(copy_db(tmp_path / "after.db"),
                      order_statements("MWS1050", None, "utah.cellar@example.com", ca_ship,
                                       GUEST_PAY, 68.97, 14.95, 86.87, 3, [CHIANTI]))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "db_new_order_row"


def test_wrong_quantity_delta_fail(tmp_path):
    n = 9
    run_dir = honest_run(tmp_path / f"wq{n}", n)
    initial = copy_db(tmp_path / "init.db")
    after = mutate_db(copy_db(tmp_path / "after.db"),
                      order_statements("MWS1050", None, GUEST_EMAIL, GUEST_SHIP, GUEST_PAY,
                                       112.99, 14.95, 130.89, 2,
                                       [GC100, {**CINGUETTO2, "quantity": 1}]))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "db_order_items_giftcard_plus_sparkling"


def test_wrong_address_delta_fail(tmp_path):
    n = 6
    run_dir = honest_run(tmp_path / f"wa{n}", n)
    initial = copy_db(tmp_path / "init.db")
    chicago = {"name": "Carol Davis", "line1": "820 N Michigan Ave", "city": "Chicago",
               "state": "IL", "zip": "60611"}
    after = mutate_db(copy_db(tmp_path / "after.db"),
                      address_statements(3, "Kayla Davis", "118 Larimer St", "Apt 4",
                                         "Denver", "CO", "80204", "(303) 555-0148")
                      + order_statements("MWS1050", 3, CAROL, chicago,
                                         "Mastercard ending in 2222", 126.63, 0.0,
                                         129.58, 8, [CLOSED2, MARTHAS])
                      + delete_cart_statements([5, 6]))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "db_new_order_row"


def test_collateral_delta_fail(tmp_path):
    n = 1
    run_dir = honest_run(tmp_path / f"col{n}", n)
    initial = copy_db(tmp_path / "init.db")
    after = mutate_db(stateful_after_db(n, tmp_path / "after.db"),
                      [("UPDATE site_texts SET value = 'tampered' WHERE id = 1", ())])
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "no_collateral_writes"


# ------------------------------------------------------------------ package tampering fail-closed
def test_task_id_mismatch_fail(tmp_path):
    run_dir = honest_run(tmp_path / "tid", 1)
    traj_file = run_dir / "trajectory.json"
    traj = json.loads(traj_file.read_text())
    traj["task_id"] = "MacysWineShop--2"
    traj_file.write_text(json.dumps(traj))
    initial = copy_db(tmp_path / "init.db")
    after = stateful_after_db(1, tmp_path / "after.db")
    verdict = run_verifier(1, run_dir, initial, after)
    assert verdict["pass"] is False


def test_offsite_url_fail(tmp_path):
    run_dir = honest_run(tmp_path / "off", 0)
    traj_file = run_dir / "trajectory.json"
    traj = json.loads(traj_file.read_text())
    traj["steps"][0]["url"] = "https://example.com/evil"
    traj_file.write_text(json.dumps(traj))
    initial = copy_db(tmp_path / "init.db")
    after = stateful_after_db(0, tmp_path / "after.db")
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict["pass"] is False


def test_missing_screenshot_fail(tmp_path):
    run_dir = honest_run(tmp_path / "shot", 2)
    (run_dir / "screenshots" / "step_001.png").unlink()
    initial = copy_db(tmp_path / "init.db")
    after = stateful_after_db(2, tmp_path / "after.db")
    verdict = run_verifier(2, run_dir, initial, after)
    assert verdict["pass"] is False


def test_nondone_trajectory_fail(tmp_path):
    run_dir = honest_run(tmp_path / "nd", 3)
    traj_file = run_dir / "trajectory.json"
    traj = json.loads(traj_file.read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    traj_file.write_text(json.dumps(traj))
    initial = copy_db(tmp_path / "init.db")
    after = stateful_after_db(3, tmp_path / "after.db")
    verdict = run_verifier(3, run_dir, initial, after)
    assert verdict["pass"] is False


def test_tampered_seed_fail(tmp_path):
    run_dir = honest_run(tmp_path / "seed", 5)
    initial = mutate_db(copy_db(tmp_path / "init.db"),
                        [("UPDATE products SET price = 1.0 WHERE id = 1", ())])
    after = stateful_after_db(5, tmp_path / "after.db")
    verdict = run_verifier(5, run_dir, initial, after)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True


def test_unavailable_db_fail(tmp_path, monkeypatch):
    run_dir = honest_run(tmp_path / "nodb", 7)
    verdict = run_verifier(7, run_dir, tmp_path / "missing-init.db",
                           tmp_path / "missing-after.db")
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True
