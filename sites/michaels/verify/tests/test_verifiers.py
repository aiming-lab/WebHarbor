"""Deterministic verifier contract tests for the 19 Michaels tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a wrong
answer MUST FAIL; a shortcut (correct answer — and for stateful tasks even the
correct DB delta — with homepage-only navigation) MUST FAIL: every task's
required surface is beyond the homepage. Read-only tasks MUST FAIL on a mutated
after-DB; stateful tasks MUST FAIL on a state-mismatch (no DB delta) and on a
wrong delta. Package tampering (task_id mismatch, off-site URLs, missing
screenshots, non-done trajectory, tampered seed, unavailable DB) MUST fail
closed.

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
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                      build_run, copy_db, db_one, mutate_db, noop_run,
                      run_verifier)

STATEFUL = {0, 1, 2, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18}
READ_ONLY = sorted(set(range(19)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}
CREATED = "2026-09-20 00:00:00.000000"

L3 = "level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532"
L1 = "level-1-back-stapled-canvas-by-artist-s-loft-10672808"
SB = "10-x-10-flat-white-deep-profile-shadow-box-by-studio-d-cor-10739210"
CASE = "mini-helmet-display-case-by-studio-d-cor-10403379"
WAFERS = "melt-craft-vanilla-candy-wafers-10764419"
BOARD = "36-x-48-corrugated-tri-fold-display-board-10061591"
TULLE = "6-glitter-tulle-by-celebrate-it-occasions-10217915"
GROSGRAIN = "1-4-x-10yd-grosgrain-ribbon-by-celebrate-it-classic-10264009"
DAHLIA = "15-mauve-pale-pink-dahlia-mix-bush-by-ashland-10811002"
MD = "national-geographic-metal-detector-starter-kit-10758215"
SC = "snap-circuits-explorer-100-experiments-10567231"
DBOX = "8-x-12-black-collection-display-box-by-studio-d-cor-10738990"
JOY = "cricut-joy-2-in-jade-green-essential-bundle-10815288"
EXPLORE = "cricut-explore-5-in-teal-essential-bundle-with-digital-content-10816737"
CAT = "11-x-14-cat-in-library-paint-by-number-kit-by-artist-s-loft-10808381"
LUC = "light-up-black-cat-paint-by-number-acrylic-surface-kit-by-artist-s-loft-10808372"
RIBBON = "500yd-textured-curling-ribbon-by-celebrate-it-10118272"
JOURNAL = "back-to-school-6-x-8-lined-journal-with-elastic-closure-by-recollections-10807593"
PACK5 = "5-pack-16-x-20-super-value-canvas-by-artist-s-loft-10131611"
PACK10 = "10-pack-8-x-10-super-value-canvas-by-artist-s-loft-10131568"


# ---------------------------------------------------------------- navigation fixtures
def honest_steps(index: int):
    """[(path, action, params)] navigation for the honest run of task `index`."""
    def login(who):
        return [("fill", LOGIN[who]), ("fill", PASSWORD), ("click-submit", "/")]
    S = {
        0: [("/search?q=Artist%27s+Loft+canvas", "goto", {}), (f"/product/{L3}", "goto", {}),
            (f"/product/{L1}", "goto", {}), ("/login", "fill", LOGIN["alice"]),
            ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
            ("/search?q=Level+1+Back+Stapled+Canvas", "goto", {}),
            (f"/product/{L1}", "goto", {}), ("/cart", "goto", {}), ("/checkout", "goto", {}),
            ("/order/confirmation/MI26092301003", "goto", {})],
        1: [("/login", "fill", LOGIN["david"]), ("/login", "fill", PASSWORD),
            ("/login", "click-submit", "/"), ("/search?q=Studio+Decor+shadow+box", "goto", {}),
            (f"/product/{SB}", "goto", {}), ("/search?q=Mini+Helmet+Display+Case", "goto", {}),
            (f"/product/{CASE}", "goto", {}), ("/cart", "goto", {}), ("/checkout", "goto", {}),
            ("/order/confirmation/MI26092304002", "goto", {})],
        2: [("/login", "fill", LOGIN["bob"]), ("/login", "fill", PASSWORD),
            ("/login", "click-submit", "/"), ("/cart", "goto", {}),
            ("/search?q=MDF+letter", "goto", {}),
            ("/product/13-white-mdf-uppercase-letter-by-make-market-10281316", "goto", {}),
            ("/cart", "goto", {})],
        3: [("/login", "fill", LOGIN["alice"]), ("/login", "fill", PASSWORD),
            ("/login", "click-submit", "/"), ("/account", "goto", {}),
            ("/account/order/MI2609180101002", "goto", {})],
        4: [("/search?q=Artist%27s+Loft+canvas", "goto", {}), (f"/product/{L3}", "goto", {}),
            (f"/product/{L3}/reviews", "goto", {}),
            ("/search?q=Level+1+Back+Stapled+Canvas", "goto", {}),
            (f"/product/{L1}", "goto", {}), (f"/product/{L1}/reviews", "goto", {})],
        5: [("/store-locator", "goto", {}), ("/store-locator?q=Cary", "goto", {}),
            ("/store-locator?q=Durham", "goto", {}), ("/store-locator?q=NC", "goto", {})],
        6: [("/login", "fill", LOGIN["alice"]), ("/login", "fill", PASSWORD),
            ("/login", "click-submit", "/"), ("/classes", "goto", {}),
            ("/account/registrations", "goto", {}),
            ("/classes?category=Fabric%20%26%20Sewing", "goto", {})],
        7: [("/login", "goto", {}), ("/register", "fill", "priya.k@example.com"),
            ("/register", "fill", "CraftsCorner#2026"), ("/register", "click-submit", "/"),
            ("/account", "goto", {}), ("/account/payment", "fill", "4012888888886621"),
            ("/account/payment", "fill", "9"), ("/account/payment", "fill", "2027"),
            ("/account/payment", "click-submit", "/account/payment"),
            ("/search?q=Textured+Curling+Ribbon", "goto", {}), (f"/product/{RIBBON}", "goto", {}),
            ("/search?q=lined+journal", "goto", {}), (f"/product/{JOURNAL}", "goto", {}),
            ("/cart", "fill", "GETMY30"), ("/cart", "click-submit", "/cart"),
            ("/checkout", "goto", {}), ("/order/confirmation/MI26092305001", "goto", {})],
        8: [("/search?q=Super+Value+Canvas", "goto", {}), (f"/product/{PACK5}", "goto", {}),
            (f"/product/{PACK10}", "goto", {}), ("/login", "fill", LOGIN["alice"]),
            ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
            ("/search?q=5+Pack+16+Super+Value+Canvas", "goto", {}),
            (f"/product/{PACK5}", "goto", {}), ("/cart", "goto", {})],
        9: [("/savings", "goto", {}), ("/coupon-policy-and-price-guarantee", "goto", {}),
            ("/login", "fill", LOGIN["bob"]), ("/login", "fill", PASSWORD),
            ("/login", "click-submit", "/"), ("/cart", "goto", {}),
            ("/cart", "fill", "GETMY30"), ("/cart", "click-submit", "/cart")],
        10: [("/login", "fill", LOGIN["carol"]), ("/login", "fill", PASSWORD),
             ("/login", "click-submit", "/"), ("/account", "goto", {}), ("/wishlist", "goto", {}),
             ("/search?q=Glitter+Tulle", "goto", {}), (f"/product/{TULLE}", "goto", {}),
             ("/search?q=Grosgrain+Ribbon", "goto", {}), (f"/product/{GROSGRAIN}", "goto", {}),
             ("/account", "goto", {}), ("/wishlist", "goto", {})],
        11: [("/shop/floral", "goto", {}),
             ("/shop/floral?availability=pickup&sort=price_low", "goto", {}),
             (f"/product/{DAHLIA}", "goto", {}), ("/login", "fill", LOGIN["david"]),
             ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
             ("/cart", "goto", {})],
        12: [("/login", "fill", LOGIN["david"]), ("/login", "fill", PASSWORD),
             ("/login", "click-submit", "/"), ("/account", "goto", {}),
             ("/account/order/MI2609220404001", "goto", {}),
             ("/search?q=Corrugated+Tri-Fold+Display+Board", "goto", {}),
             (f"/product/{BOARD}", "goto", {}), ("/cart", "goto", {})],
        13: [("/search?q=Glitter+Tulle", "goto", {}), (f"/product/{TULLE}", "goto", {}),
             ("/login", "fill", LOGIN["carol"]), ("/login", "fill", PASSWORD),
             ("/login", "click-submit", "/"), ("/search?q=6%22+Glitter+Tulle", "goto", {}),
             (f"/product/{TULLE}", "goto", {}), ("/cart", "fill", "GETMY30"),
             ("/cart", "click-submit", "/cart")],
        14: [("/login", "fill", LOGIN["bob"]), ("/login", "fill", PASSWORD),
             ("/login", "click-submit", "/"), ("/search?q=Metal+Detector+Starter+Kit", "goto", {}),
             (f"/product/{MD}", "goto", {}), ("/search?q=Snap+Circuits+Explorer", "goto", {}),
             (f"/product/{SC}", "goto", {}), ("/cart", "goto", {})],
        15: [("/login", "fill", LOGIN["alice"]), ("/login", "fill", PASSWORD),
             ("/login", "click-submit", "/"), ("/account", "goto", {}),
             ("/account/profile", "fill", "(206) 555-0102"),
             ("/account/profile", "click-submit", "/account/profile"),
             ("/account/addresses", "fill", "2201 Alki Ave SW"),
             ("/account/addresses", "click-submit", "/account/addresses"),
             ("/search?q=Black+Collection+Display+Box", "goto", {}),
             (f"/product/{DBOX}", "goto", {}), ("/cart", "goto", {}), ("/checkout", "goto", {}),
             ("/order/confirmation/MI26092301003", "goto", {})],
        16: [("/search?q=Cricut", "goto", {}), (f"/product/{JOY}", "goto", {}),
             (f"/product/{EXPLORE}", "goto", {}), ("/login", "fill", LOGIN["bob"]),
             ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
             ("/search?q=Cricut+Joy+2+Jade+Green+Essential", "goto", {}),
             (f"/product/{JOY}", "goto", {}), ("/cart", "goto", {})],
        17: [("/search?q=Level+3+Gallery+Wrapped+Heavy+Duty+Canvas", "goto", {}),
             (f"/product/{L3}", "goto", {}), ("/login", "fill", LOGIN["carol"]),
             ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
             ("/search?q=Level+3+Gallery+Wrapped+Heavy+Duty+Canvas", "goto", {}),
             (f"/product/{L3}", "goto", {}), ("/cart", "goto", {})],
        18: [("/search?q=paint-by-number", "goto", {}), (f"/product/{CAT}", "goto", {}),
             (f"/product/{LUC}", "goto", {}), ("/login", "fill", LOGIN["alice"]),
             ("/login", "fill", PASSWORD), ("/login", "click-submit", "/"),
             ("/search?q=Light+Up+Black+Cat+Paint-by-Number", "goto", {}),
             (f"/product/{LUC}", "goto", {}), ("/cart", "fill", "GETMY30"),
             ("/cart", "click-submit", "/cart")],
    }
    return S[index]


def apply_steps(b: RunBuilder, steps):
    for path, action, params in steps:
        if action == "fill":
            b.fill(path, params)
        elif action == "click-submit":
            b.step(path, "click", {"selector": "button[type=submit]"}, url_after=params)
        else:
            b.step(path, action, params)
    return b


# ---------------------------------------------------------------- honest answers
def honest_answer(index: int) -> str:
    A = {
        0: ("The Level 1 Back Stapled Canvas 16\" x 20\" at $15.99 is cheaper than the "
            "Level 3 Gallery Wrapped 16\" x 20\" at $32.99 (Level 3 rating 4.8 with 16,705 "
            "reviews; Level 1 rating 4.7 with 8,708). Bought two Level 1 canvases with "
            "code GETMY30 shipped home on the Visa ending 4242. Order MI26092301003, "
            "order total $68.30."),
        1: ("Using the Buy One Get One FREE mix & match promo: Flat White Deep Profile "
            "Shadow Box $17.49 and Mini Helmet Display Case $12.49. BOGO discount "
            "$12.49. Order MI26092304002 with store pickup on the Discover card, order "
            "total $38.74."),
        2: ("Removed the corrugated display board and swapped the MDF letter B for a 13\" "
            "White MDF Uppercase Letter S; raised the candy wafers to 4 bags. Final cart: "
            "13\" White MDF Uppercase Letter S at $6.99 each (qty 1) and Melt Craft Vanilla "
            "Candy Wafers at $4.99 per bag (qty 4). New cart subtotal $26.95, new order "
            "total $35.43."),
        3: ("Order MI2609180101002 is Delivered. Item: 6 x 6\" x 20yd. Tulle Fabric by "
            "Celebrate It Occasions (White) at $4.99 each. Subtotal $29.94, promo "
            "discount $8.98 (30% GETMY30), shipping FREE (pickup), tax $1.94, total "
            "$22.90, charged to Visa ****4242, picked up at Parkway Supercenter in "
            "Tukwila, WA."),
        4: ("Level 3 Gallery Wrapped Heavy Duty Canvas: 14,630 five-star reviews, 244 "
            "one-star, average 4.8 from 16,705 reviews. Level 1 Back Stapled Canvas: "
            "7,028 five-star, 142 one-star, average 4.7 from 8,708 reviews."),
        5: ("The Cary store is Crossroads Plaza at 340 Crossroads Blvd, Cary, NC "
            "27518-6895, phone (919) 851-6001. Sunday hours 10:00 AM - 07:00 PM. It "
            "offers balloon inflation and custom framing. The New Hope Commons store in "
            "Durham also offers balloon inflation, and its Sunday hours are 10:00 AM - "
            "07:00 PM. Other North Carolina locations with balloon inflation: Park Road "
            "Shopping Center (Charlotte), New Hope Commons (Durham), RAL-DURHAM~NORTH, NC "
            "(Durham), and Park West Village (Morrisville) — 4 others."),
        6: ("Registered Alice for the class \"Kids Club: Halloween Bat Mask\" on "
            "2026-09-28, 03:00 pm - 04:00 pm PDT, on the Virtual Classroom - Vimeo "
            "platform, hosted by Learn With Michaels. The site confirmed: Registered for "
            "\"Kids Club: Halloween Bat Mask\" on 2026-09-28 at 03:00 pm - 04:00 pm PDT "
            "(Virtual Classroom - Vimeo). The account's Class Registrations page confirms "
            "the signup: Registered 2026-09-23 for Alice Johnson. The shortest NEW Fabric & "
            "Sewing tutorial is \"How to Sew a Napkin\", 6 min."),
        7: ("Created the account for priya.k@example.com and added the Visa ending "
            "6621 expiring 09/2027. Ordered the 500yd. Textured Curling Ribbon ($6.49) "
            "and the Back to School 6\" x 8\" Lined Journal ($2.39) with GETMY30 and "
            "store pickup. Order MI26092305001, total $6.80."),
        8: ("Both packs are $12.99. The 5 Pack of 16\" x 20\" gives 5 x 320 = 1,600 sq "
            "in, about 123.2 sq in per dollar. The 10 Pack of 8\" x 10\" gives 10 x 80 "
            "= 800 sq in, about 61.6 sq in per dollar. The 5 Pack gives more canvas "
            "area per dollar. Raised the 5 pack in the cart to 2 packs: new subtotal "
            "$70.33."),
        9: ("The coupon is 30% OFF Any One Regular Price Item, valid in store only, "
            "expiring 2026-09-24 (valid from 2026-09-18). The Buy One Get One frames "
            "promo ends 2026-09-26. GETMY30 (online only) excludes sale & clearance, "
            "tech, Cricut, LEGO, Sizzix, Splendid, Simply Tidy, and Brother & Janome "
            "machines. The policy limits AORPI coupons to one coupon per product and "
            "one coupon of each type per day, so she may use one per day. She cannot "
            "stack GETMY30 on top of the in-store coupon: GETMY30 is online only while "
            "this coupon is in-store only, so they apply to separate channels and cannot "
            "be combined. Applied GETMY30 to Bob's cart: discount $7.19, new order total "
            "$24.31."),
        10: ("Removed the three canvas items from the wishlist and saved the 6\" "
             "Glitter Tulle in Fuchsia and the 1/4\" x 10yd. Grosgrain Ribbon. The "
             "wishlist now shows 3 items."),
        11: ("The cheapest floral item available for Store Pickup is the 15\" Mauve & "
             "Pale Pink Dahlia Mix Bush by Ashland at $5.19 each. Added three to "
             "David's cart. New subtotal $33.54."),
        12: ("The most recent order is MI2609220404001, placed 2026-09-22, status "
             "Processing: 1 x 36\" x 48\" Corrugated Tri-Fold Display Board in Black, "
             "total $6.54, charged to Visa ****4242, pickup. Started the reorder in "
             "White: updated cart total $32.17."),
        13: ("The 6\" Glitter Tulle comes in 10 colors: Fuchsia, Pink, Purple, "
             "White/Gold, Turquoise, Silver, Iridescent White, Red, Neon Orange, and "
             "Neon Pink, at $4.99 per roll. Added three Fuchsia rolls with GETMY30: "
             "discount $17.81, new order total $51.41."),
        14: ("National Geographic Metal Detector Starter Kit $50.99 and Snap Circuits "
             "Explorer 100 Experiments $33.74. With the Buy One Get One 50% off mix & "
             "match promo the cart shows a BOGO discount of $16.87. New order total "
             "$100.31."),
        15: ("Updated the profile phone to (206) 555-0102 and added the Beach House "
             "address (2201 Alki Ave SW, Seattle, WA 98116). Ordered the 8\" x 12\" "
             "Black Collection Display Box ($13.49) shipped to the Beach House on the "
             "Mastercard ending 5309. Order MI26092301003, order total $77.38."),
        16: ("Cricut Joy 2 in Jade Green & Essential Bundle: $139.00, rating 4.7 (129 "
             "reviews). Cricut Explore 5 in Teal & Essential Bundle: $249.00, rating "
             "4.2 (116 reviews). The Joy 2 has the higher rating, so I added it to "
             "Bob's cart. New cart subtotal $162.96."),
        17: ("Yes — the description confirms the canvas is made with archival-quality "
             "natural cotton and is gesso primed. The largest size is 48\" x 48\" at "
             "$109.99, located in Aisle 14 at Parkway Supercenter (98188). Added it to "
             "Carol's cart: new subtotal $154.40."),
        18: ("Cat in Library Paint-by-Number Kit: $6.99, rating 4.3 (6 reviews). Light "
             "Up Black Cat Paint-by-Number Acrylic Surface Kit: $5.99, rating 4.5 (6 "
             "reviews). The Light Up Black Cat is higher rated, so I added two with "
             "GETMY30: discount $20.80, new order total $59.00."),
    }
    return A[index]


def wrong_answer(index: int) -> str:
    return ("I looked around the site but I am not sure; the answer is 999 and "
            "nothing else matches.")


# ---------------------------------------------------------------- stateful mutations
def order_sql(conf, user_id, method, addr, brand, last4, subtotal, discount,
               shipping, tax, total, promo):
    return ("INSERT INTO orders (user_id, order_number, status, placed_at, "
            "delivery_method, address_line, card_brand, card_last4, subtotal, "
            "discount, shipping, tax, total, promo_code) VALUES "
            "(?, ?, 'Processing', '2026-09-23', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, conf, method, addr, brand, last4, subtotal, discount,
             shipping, tax, total, promo))


def item_sql(order_id, product_id, name, sku, color, qty, price):
    return ("INSERT INTO order_items (order_id, product_id, name, variant_sku, "
            "color, qty, unit_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, product_id, name, sku, color, qty, price))


def added_order_id(db: Path) -> int:
    return db_one(db, "SELECT MAX(id) FROM orders")


def stateful_statements(index: int, variant: str = "ok"):
    """[(sql, params)] turning a seed copy into the honest after-state (or a wrong one)."""
    if index == 0:
        if variant == "wrong_total":
            return [order_sql("MI26092301003", 1, "Ship",
                              "1420 Rainier Ave S, Seattle, WA 98144", "Visa", "4242",
                              89.32, 26.80, 0.0, 5.78, 99.99, "GETMY30")]
        return [order_sql("MI26092301003", 1, "Ship",
                          "1420 Rainier Ave S, Seattle, WA 98144", "Visa", "4242",
                          89.32, 26.80, 0.0, 5.78, 68.30, "GETMY30"),
                ("DELETE FROM cart_items WHERE user_id = 1", ()),
                item_sql(6, 294, "Level 3 Gallery Wrapped Heavy Duty Canvas by Artist's Loft®",
                         "10233037", '4" x 4"', 2, 7.49),
                item_sql(6, 106, '5 Pack 16" x 20" Super Value Canvas by Artist\'s Loft®',
                         "", "", 1, 12.99),
                item_sql(6, 13, "11\" x 14\" Double Mat By Studio Décor®, 8\" x 10\" Opening",
                         "10084039", "White/White", 3, 9.79),
                item_sql(6, 291, "Level 1 Back Stapled Canvas by Artist's Loft®",
                         "10672550", '16" x 20"', 2, 15.99)]
    if index == 1:
        if variant == "wrong_discount":
            return [order_sql("MI26092304002", 4, "Pickup",
                              "445 N Canyons Pkwy, Livermore, CA 94551", "Discover", "6442",
                              47.95, 9.99, 0.0, 3.28, 38.74, "")]
        return [order_sql("MI26092304002", 4, "Pickup",
                          "445 N Canyons Pkwy, Livermore, CA 94551", "Discover", "6442",
                          47.95, 12.49, 0.0, 3.28, 38.74, ""),
                ("DELETE FROM cart_items WHERE user_id = 4", ()),
                item_sql(6, 114, '6" Glitter Tulle by Celebrate It® Occasions™',
                         "10217907", "Fuchsia", 1, 4.99),
                item_sql(6, 141, '8" x 10" Double Mat By Studio Décor®, 5" x 7" Opening',
                         "10083921", "White/White", 2, 6.49),
                item_sql(6, 5, '10" x 10" Flat White Deep Profile Shadow Box by Studio Décor®',
                         "", "", 1, 17.49),
                item_sql(6, 302, "Mini Helmet Display Case by Studio Décor®",
                         "", "", 1, 12.49)]
    if index == 2:
        if variant == "wrong_qty":
            return [("DELETE FROM cart_items WHERE user_id = 2 AND variant_sku = '10044460'", ()),
                    ("DELETE FROM cart_items WHERE user_id = 2 AND variant_sku = '10281304'", ()),
                    ("INSERT INTO cart_items (user_id, product_id, variant_sku, color, qty, "
                     "added_at) VALUES (2, 37, '10281322', 'S', 1, '2026-09-20 00:00:00.000000')", ()),
                    ("UPDATE cart_items SET qty = 5 WHERE user_id = 2 AND variant_sku = '10764405'", ())]
        return [("DELETE FROM cart_items WHERE user_id = 2 AND variant_sku = '10044460'", ()),
                ("DELETE FROM cart_items WHERE user_id = 2 AND variant_sku = '10281304'", ()),
                ("INSERT INTO cart_items (user_id, product_id, variant_sku, color, qty, "
                 "added_at) VALUES (2, 37, '10281322', 'S', 1, '2026-09-20 00:00:00.000000')", ()),
                ("UPDATE cart_items SET qty = 4 WHERE user_id = 2 AND variant_sku = '10764405'", ())]
    if index == 6:
        if variant == "wrong_class":
            return [("INSERT INTO class_registrations (user_id, class_event_id, "
                     "registered_at, attendee_name) VALUES (1, 7, '2026-09-23', "
                     "'Alice Johnson')", ())]
        return [("INSERT INTO class_registrations (user_id, class_event_id, "
                 "registered_at, attendee_name) VALUES (1, 4, '2026-09-23', "
                 "'Alice Johnson')", ())]
    if index == 7:
        if variant == "wrong_card":
            return [("INSERT INTO users (email, password_hash, name, phone, "
                     "rewards_member, created_at) VALUES ('priya.k@example.com', 'x', 'Priya K', "
                     "'', 1, '2026-01-15 00:00:00.000000')", ()),
                    ("INSERT INTO payment_cards (user_id, label, brand, last4, "
                     "exp_month, exp_year, is_default) VALUES (5, 'Personal', "
                     "'Mastercard', '6621', 9, 2027, 0)", ()),
                    order_sql("MI26092305001", 5, "Pickup",
                              "Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, "
                              "Tukwila, WA 98188", "Mastercard", "6621",
                              8.88, 2.66, 0.0, 0.58, 6.80, "GETMY30")]
        return [("INSERT INTO users (email, password_hash, name, phone, "
                 "rewards_member, created_at) VALUES ('priya.k@example.com', 'x', 'Priya K', "
                 "'', 1, '2026-01-15 00:00:00.000000')", ()),
                ("INSERT INTO payment_cards (user_id, label, brand, last4, "
                 "exp_month, exp_year, is_default) VALUES (5, 'Personal', 'Visa', "
                 "'6621', 9, 2027, 0)", ()),
                order_sql("MI26092305001", 5, "Pickup",
                          "Store Pickup - Parkway Supercenter, 17400 Southcenter Pkwy, "
                          "Tukwila, WA 98188", "Visa", "6621",
                          8.88, 2.66, 0.0, 0.58, 6.80, "GETMY30"),
                item_sql(6, 110, "500yd. Textured Curling Ribbon by Celebrate It™",
                         "10118256", "White", 1, 6.49),
                item_sql(6, 166, 'Back to School 6" x 8" Lined Journal with Elastic Closure '
                         "by Recollections™", "10807593", "Flowers", 1, 2.39)]
    if index == 8:
        if variant == "wrong_qty":
            return [("UPDATE cart_items SET qty = 3 WHERE user_id = 1 AND product_id = 106", ())]
        return [("UPDATE cart_items SET qty = 2 WHERE user_id = 1 AND product_id = 106", ())]
    if index == 10:
        if variant == "wrong_swap":
            return [("DELETE FROM wishlist_items WHERE user_id = 3 AND product_id IN (115, 116, 118)", ()),
                    ("INSERT INTO wishlist_items (user_id, product_id, added_at) VALUES "
                     "(3, 114, '2026-09-18 00:00:00.000000')", ())]
        return [("DELETE FROM wishlist_items WHERE user_id = 3 AND product_id IN (115, 116, 118)", ()),
                ("INSERT INTO wishlist_items (user_id, product_id, added_at) VALUES "
                 "(3, 114, '2026-09-18 00:00:00.000000')", ()),
                ("INSERT INTO wishlist_items (user_id, product_id, added_at) VALUES "
                 "(3, 42, '2026-09-18 00:00:00.000000')", ())]
    if index == 11:
        if variant == "wrong_product":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (4, 70, '', '', 3, '2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (4, 49, '', '', 3, '2026-09-20 00:00:00.000000')", ())]
    if index == 12:
        if variant == "wrong_color":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (4, 91, '10044460', 'Black', 1, "
                     "'2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (4, 91, '10061591', 'White', 1, "
                 "'2026-09-20 00:00:00.000000')", ())]
    if index == 13:
        if variant == "wrong_color":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (3, 114, '10217911', 'Pink', 3, "
                     "'2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (3, 114, '10217907', 'Fuchsia', 3, "
                 "'2026-09-20 00:00:00.000000')", ())]
    if index == 14:
        if variant == "wrong_items":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (2, 307, '', '', 1, '2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (2, 307, '', '', 1, '2026-09-20 00:00:00.000000')", ()),
                ("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (2, 329, '', '', 1, '2026-09-20 00:00:00.000000')", ())]
    if index == 15:
        if variant == "wrong_phone":
            return [("UPDATE users SET phone = '(206) 555-0199' WHERE id = 1", ()),
                    ("INSERT INTO addresses (user_id, label, line1, line2, city, state, "
                     "zip_code, is_default) VALUES (1, 'Beach House', '2201 Alki Ave SW', "
                     "'', 'Seattle', 'WA', '98116', 0)", ()),
                    order_sql("MI26092301003", 1, "Ship",
                              "2201 Alki Ave SW, Seattle, WA 98116", "Mastercard", "5309",
                              70.83, 0.0, 0.0, 6.55, 77.38, ""),
                    ("DELETE FROM cart_items WHERE user_id = 1", ())]
        return [("UPDATE users SET phone = '(206) 555-0102' WHERE id = 1", ()),
                ("INSERT INTO addresses (user_id, label, line1, line2, city, state, "
                 "zip_code, is_default) VALUES (1, 'Beach House', '2201 Alki Ave SW', "
                 "'', 'Seattle', 'WA', '98116', 0)", ()),
                order_sql("MI26092301003", 1, "Ship",
                          "2201 Alki Ave SW, Seattle, WA 98116", "Mastercard", "5309",
                          70.83, 0.0, 0.0, 6.55, 77.38, ""),
                ("DELETE FROM cart_items WHERE user_id = 1", ()),
                item_sql(6, 294, "Level 3 Gallery Wrapped Heavy Duty Canvas by Artist's Loft®",
                         "10233037", '4" x 4"', 2, 7.49),
                item_sql(6, 106, '5 Pack 16" x 20" Super Value Canvas by Artist\'s Loft®',
                         "", "", 1, 12.99),
                item_sql(6, 13, "11\" x 14\" Double Mat By Studio Décor®, 8\" x 10\" Opening",
                         "10084039", "White/White", 3, 9.79),
                item_sql(6, 142, '8" x 12" Black Collection Display Box by Studio Décor®',
                         "", "", 1, 13.49)]
    if index == 16:
        if variant == "wrong_product":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (2, 215, '', '', 1, '2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (2, 218, '', '', 1, '2026-09-20 00:00:00.000000')", ())]
    if index == 17:
        if variant == "wrong_size":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (3, 294, '10472519', '36\" x 36\"', 1, "
                     "'2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (3, 294, '10472520', '48\" x 48\"', 1, "
                 "'2026-09-20 00:00:00.000000')", ())]
    if index == 18:
        if variant == "wrong_product":
            return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                     "qty, added_at) VALUES (1, 10, '', '', 2, '2026-09-20 00:00:00.000000')", ())]
        return [("INSERT INTO cart_items (user_id, product_id, variant_sku, color, "
                 "qty, added_at) VALUES (1, 296, '', '', 2, '2026-09-20 00:00:00.000000')", ())]
    raise ValueError(f"task {index} is not stateful")


# ---------------------------------------------------------------- run builders
def honest_run(tmp: Path, index: int, seed: Path, variant: str = "ok") -> Path:
    root = tmp / f"honest_{index:02d}_{variant}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index, variant))
    else:
        copy_db(seed, root / "after.db")
    b = build_run(tmp, f"honest_{index:02d}_{variant}_run", f"Michaels--{index}")
    apply_steps(b, honest_steps(index))
    b.done(honest_answer(index))
    # move the run dir contents under root (tests use one dir per run)
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


def wrong_answer_run(tmp: Path, index: int, seed: Path) -> Path:
    root = tmp / f"wrong_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index))
    else:
        copy_db(seed, root / "after.db")
    b = build_run(tmp, f"wrong_{index:02d}_run", f"Michaels--{index}")
    apply_steps(b, honest_steps(index))
    b.done(wrong_answer(index))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


def shortcut_run(tmp: Path, index: int, seed: Path) -> Path:
    """Correct answer + correct DB delta, but homepage-only navigation."""
    root = tmp / f"shortcut_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index))
    else:
        copy_db(seed, root / "after.db")
    b = build_run(tmp, f"shortcut_{index:02d}_run", f"Michaels--{index}")
    b.step("/", "goto", {})
    b.done(honest_answer(index), final_path="/")
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


def state_mismatch_run(tmp: Path, index: int, seed: Path) -> Path:
    """Honest navigation + honest answer, but NO DB delta (stateless after-DB)."""
    root = tmp / f"nomatch_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp, f"nomatch_{index:02d}_run", f"Michaels--{index}")
    apply_steps(b, honest_steps(index))
    b.done(honest_answer(index))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


def mutated_readonly_run(tmp: Path, index: int, seed: Path) -> Path:
    """Honest run, but the after-DB carries an unrelated write (read-only violation)."""
    root = tmp / f"mut_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    mutate_db(seed, root / "after.db",
              [("UPDATE products SET price = price + 1 WHERE id = 1", ())])
    b = build_run(tmp, f"mut_{index:02d}_run", f"Michaels--{index}")
    apply_steps(b, honest_steps(index))
    b.done(honest_answer(index))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def seed():
    path = _acquire_seed()
    yield path


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("index", range(19))
def test_honest_pass(tmp_path, seed, index):
    run = honest_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is True, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(19))
def test_noop_fail(tmp_path, seed, index):
    run = noop_run(tmp_path, index)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(19))
def test_wrong_answer_fail(tmp_path, seed, index):
    run = wrong_answer_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(19))
def test_shortcut_fail(tmp_path, seed, index):
    run = shortcut_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fail(tmp_path, seed, index):
    run = state_mismatch_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


WRONG_DELTA_VARIANTS = {0: "wrong_total", 1: "wrong_discount", 2: "wrong_qty",
                        6: "wrong_class", 7: "wrong_card", 8: "wrong_qty",
                        10: "wrong_swap", 11: "wrong_product", 12: "wrong_color",
                        13: "wrong_color", 14: "wrong_items", 15: "wrong_phone",
                        16: "wrong_product", 17: "wrong_size", 18: "wrong_product"}


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fail(tmp_path, seed, index):
    run = honest_run(tmp_path, index, seed, variant=WRONG_DELTA_VARIANTS[index])
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", READ_ONLY)
def test_mutated_after_fail(tmp_path, seed, index):
    run = mutated_readonly_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fail(tmp_path, seed):
    root = tmp_path / "tamper_taskid"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, "tamper_taskid_run", "Michaels--9")
    apply_steps(b, honest_steps(0))
    b.done(honest_answer(0))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_offsite_url_fail(tmp_path, seed):
    root = tmp_path / "tamper_offsite"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, "tamper_offsite_run", "Michaels--0")
    apply_steps(b, honest_steps(0))
    b.step("/", "goto", {}, url="https://evil.example.com/steal")
    b.done(honest_answer(0))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_missing_screenshot_fail(tmp_path, seed):
    root = tmp_path / "tamper_shot"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, "tamper_shot_run", "Michaels--0")
    apply_steps(b, honest_steps(0))
    b.done(honest_answer(0))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    shots = sorted((root / "screenshots").glob("step_*.png"))
    shots[1].unlink()
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_nondone_trajectory_fail(tmp_path, seed):
    root = tmp_path / "tamper_nondone"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, "tamper_nondone_run", "Michaels--0")
    apply_steps(b, honest_steps(0))
    b.done(honest_answer(0), terminated=False, reason="max_steps")
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_tampered_seed_fails_closed(tmp_path, seed):
    root = tmp_path / "tamper_seed"
    root.mkdir(parents=True)
    mutate_db(seed, root / "initial.db",
              [("UPDATE products SET price = price + 1 WHERE id = 294", ())])
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, "tamper_seed_run", "Michaels--0")
    apply_steps(b, honest_steps(0))
    b.done(honest_answer(0))
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    result = run_verifier(0, root)
    assert result["pass"] is False and result.get("infra_error") is True


def test_unavailable_db_fails_closed(tmp_path, seed):
    root = tmp_path / "tamper_nodb"
    root.mkdir(parents=True)
    b = build_run(tmp_path, "tamper_nodb_run", "Michaels--0")
    apply_steps(b, honest_steps(0))
    b.done(honest_answer(0))
    import subprocess
    import sys as _sys
    verifier = Path(__file__).resolve().parents[1] / "verify_0.py"
    r = subprocess.run([_sys.executable, str(verifier), "--run_dir", str(b.root),
                        "--initial_db", "/nonexistent/x.db"], capture_output=True, text=True)
    result = json.loads(r.stdout)
    assert result["pass"] is False and result.get("infra_error") is True


# ---------------------------------------------------------------- audit hardening regressions
def answer_variant_run(tmp: Path, index: int, seed: Path, answer: str) -> Path:
    """Honest navigation + honest DB delta, but a custom final answer (used to
    regression-test the audit-hardened answer-claim checks)."""
    root = tmp / f"claimvar_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index))
    else:
        copy_db(seed, root / "after.db")
    b = build_run(tmp, f"claimvar_{index:02d}_run", f"Michaels--{index}")
    apply_steps(b, honest_steps(index))
    b.done(answer)
    for p in b.root.iterdir():
        shutil.move(str(p), root / p.name)
    shutil.rmtree(b.root)
    return root


def test_t01_wrong_bogo_discount_claim_fails(tmp_path, seed):
    """Audit escape: 'BOGO discount $12.50' passed because $12.49 also appears
    as the display case price. The discount-claim check must reject it."""
    answer = honest_answer(1).replace("BOGO discount $12.49", "BOGO discount $12.50")
    run = answer_variant_run(tmp_path, 1, seed, answer)
    result = run_verifier(1, run)
    assert result["pass"] is False, json.dumps(result, indent=1)
    assert result["reason"] == "answer_bogo_discount_claim"


def test_t08_false_winner_claim_fails(tmp_path, seed):
    """Audit escape: 'The 10 Pack gives more canvas area per dollar' passed via
    the incidental 'Raised the 5 pack' mention. The winner check must reject it."""
    answer = ("Both packs are $12.99. The 10 Pack gives more canvas area per "
              "dollar. Raised the 5 pack in the cart to 2 packs: new subtotal "
              "$70.33.")
    run = answer_variant_run(tmp_path, 8, seed, answer)
    result = run_verifier(8, run)
    assert result["pass"] is False, json.dumps(result, indent=1)
    assert result["reason"] == "answer_winner_5pack"


@pytest.mark.parametrize("answer", [
    # winner as the subject of the comparative claim
    ("Both packs are $12.99. The 5 Pack of 16\" x 20\" gives 1,600 sq in "
     "(123.2 sq in per dollar); the 10 Pack of 8\" x 10\" gives 800 sq in "
     "(61.6 per dollar). The 5 Pack gives more canvas area per dollar. "
     "Raised the 5 pack in the cart to 2 packs: new subtotal $70.33."),
    # comparative phrasing with the loser ahead of the winner (no false claim)
    ("Both packs are $12.99. Compared to the 10 Pack, the 5 Pack gives more "
     "canvas area per dollar: 5 x 320 = 1,600 sq in vs 10 x 80 = 800 sq in. "
     "Raised the 5 pack in the cart to 2 packs: new subtotal $70.33."),
    # reversed winner form + explicit loser 'less' statement
    ("More canvas area per dollar: the 5 Pack (123.2 sq in/$ vs 61.6). The "
     "10 Pack gives less. Raised the 5 pack in the cart to 2 packs: new "
     "subtotal $70.33."),
])
def test_t08_honest_winner_phrasings_pass(tmp_path, seed, answer):
    run = answer_variant_run(tmp_path, 8, seed, answer)
    result = run_verifier(8, run)
    assert result["pass"] is True, json.dumps(result, indent=1)


def test_t10_wrong_count_claim_fails(tmp_path, seed):
    """Audit escape: 'The wishlist now shows 4 items' passed because 'three'
    appeared in 'removed the three canvas items'. The count-claim check must
    reject it."""
    answer = honest_answer(10).replace("shows 3 items", "shows 4 items")
    run = answer_variant_run(tmp_path, 10, seed, answer)
    result = run_verifier(10, run)
    assert result["pass"] is False, json.dumps(result, indent=1)
    assert result["reason"] == "answer_wishlist_count_claim"


@pytest.mark.parametrize("answer", [
    # before/after phrasing: the earlier count must not count as a claim
    ("Removed the three canvas items from the wishlist and saved the 6\" "
     "Glitter Tulle in Fuchsia and the 1/4\" x 10yd. Grosgrain Ribbon. The "
     "wishlist previously showed 4 items; it now shows 3."),
    # word-form count
    ("Removed the three canvas items from the wishlist and saved the 6\" "
     "Glitter Tulle in Fuchsia and the 1/4\" x 10yd. Grosgrain Ribbon. The "
     "wishlist now holds three items."),
])
def test_t10_honest_count_phrasings_pass(tmp_path, seed, answer):
    run = answer_variant_run(tmp_path, 10, seed, answer)
    result = run_verifier(10, run)
    assert result["pass"] is True, json.dumps(result, indent=1)
