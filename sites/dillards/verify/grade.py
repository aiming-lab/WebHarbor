"""Shared deterministic DILLARDS task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED in answers.py (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (names / money / counts /
     phones / codes / dates, negation-aware)
  4. DB after-state: read-only tasks leave every table unchanged; the stateful
     tasks (15, 18, 19, 20, 21, 24, 28, 29, 30) must produce exactly the
     requested rows/fields and preserve the rest.

Task interpretation notes:
  - T3 reads variant prices directly from the product page after size selection.
  - T13 targets the All Seasons Tech jeans and binds their sale/original prices
    to the corresponding labels.
  - T18 says "from your recent order": the Lancome Lash Idole mascara is in
    Carol's In-Transit order D2609180298 (the UI allows returns from it; her
    delivered order contains different items). The verifier anchors on the
    mascara item + reason + method + credit amount.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, scalar, preserved,
    new_rows, removed_rows, tables_unchanged, navigated_path, navigated_prefix,
    navigated_query, navigated_url_contains, contains_count, contains_money,
    affirm_number, affirm_money, affirm_score, affirm_score2, contains_phone,
    affirms, affirms_any, contains_any, contains_number, norm, final_answer,
    step_text, sentence_count,
)
import answers as A

STATEFUL = {15, 18, 19, 20, 21, 24, 28, 29, 30}

# URL substring each task's evidence screenshot must be bound to (the page the
# task depends on; anti "answer without opening the page" shortcut).
SHOT_ANCHORS = {
    0: "/c/women-dresses", 1: "/c/men-shirts", 2: "/c/women-dresses/sale",
    3: "/p/chanel-coco-mademoiselle", 4: "/c/women-sweaters",
    5: "/c/shoes-women-shoes", 6: "/p/levis-318-shaping",
    7: "/p/antonio-melani-carter", 8: "/p/polo-ralph-lauren-classic-fit-solid-mesh-polo-shirt",
    9: "/p/alex-marie-kaitlin", 10: "/p/timberland-mens-premium-waterproof-boots",
    11: "/p/brahmin-melbourne-collection-ady", 12: "/search-term/",
    13: "/p/levis-511-slim-fit-all-seasons-tech-jeans/511371759", 14: "/search-term/", 15: "/order-confirmation/",
    16: "/account/orders/4", 17: "/account/orders/2",
    18: "/account/returns", 19: "/bag", 20: "/account/wishlist",
    21: "/account/wishlist", 22: "/registry/114815098", 23: "/registry/114802551",
    24: "/registry/", 25: "/stores", 26: "/stores", 27: "/c/DillardsCard",
    28: "/account/paybill", 29: "/p/alex-marie-kaitlin", 30: "/giftcards",
}


def _coco_size_price(final, size, price):
    """Bind each ounce size to its own price; accept ordinary prose/tables."""
    amount = size.split()[0]
    matches = list(re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:oz\.?|ounces?)", final, re.I))
    claims = [final[m.end():matches[k + 1].start() if k + 1 < len(matches) else len(final)]
              for k, m in enumerate(matches) if m.group(1) == amount]
    def valid(claim):
        dollars = [a or b for a, b in re.findall(
            r"(?:\$|USD\s*)([\d,]+(?:\.\d{1,2})?)|([\d,]+(?:\.\d{1,2})?)\s*(?:USD|dollars)", claim, re.I)]
        return bool(dollars) and all(abs(float(v.replace(',', '')) - price) < .005 for v in dollars)
    return bool(claims) and all(valid(c) for c in claims)


def _jeans_prices(final, sale, original):
    """Accept natural labeled prices while rejecting reversed sale/original values."""
    labels = list(re.finditer(
        r"\b(now|currently|current(?: sale)?(?: price)?|sale(?: price)?|"
        r"original(?:ly)?(?: price)?|was|regular(?: price)?)\b", final, re.I))
    seen = set()
    for index, label in enumerate(labels):
        claim = final[label.end():labels[index + 1].start() if index + 1 < len(labels) else len(final)]
        amount = re.search(r"(?<![\d.])(?:\$|USD\s*)?(\d+(?:,\d{3})*(?:\.\d{1,2})?)(?![\d.])", claim)
        if amount is None:
            continue
        kind = 'original' if re.match(r'original|was|regular', label.group(), re.I) else 'sale'
        expected = original if kind == 'original' else sale
        if abs(float(amount.group(1).replace(',', '')) - expected) > .005 or not affirm_money(claim, expected):
            return False
        seen.add(kind)
    return seen == {'sale', 'original'}


def grade(number, emit=True, task_id=None):
    args = parse_args()
    j = Judge(task_id or f"Dillards--{number}")
    t = load_run(args.run_dir)
    fa = final_answer(t)
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    b, a = rows(init_db), rows(after_db)
    j.bind_run(t, require_answer=True, shot_url=SHOT_ANCHORS.get(number))
    # trajectory identity: the graded package must be labeled for THIS task
    # (anti cross-task binding; a renamed/mismatched task_id is a tamper FAIL)
    j.check("trajectory_task_matches",
            str(t.get("task_id") or "").strip() == j.task_id,
            f"expected='Dillards--{number}' observed={t.get('task_id')!r}")

    if number not in STATEFUL:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            changed = tables_unchanged(init_db, after_db)
            j.check("db_unchanged", changed == [],
                    f"changed tables: {changed}" if changed else "all tables unchanged")

    # ---------------- read-only catalog / PDP / search tasks ----------------
    if number == 0:
        j.check("visited_dresses_sorted", navigated_query(t, "/c/women-dresses",
                                                          orderBy={"priceHigh", "pricehigh"}),
                "Women's Dresses sorted Price High To Low")
        j.check("answer_name", affirms(fa, A.T0_NAME), fa)
        j.check("answer_price", affirm_money(fa, A.T0_PRICE), fa)

    elif number == 1:
        j.check("visited_exclusive_shirts", navigated_path(t, "/c/men-shirts/exclusive_dillards"),
                "Men's Shirts filtered to Dillard's Exclusive")
        j.check("answer_count", contains_count(fa, A.T1_COUNT), fa)
        for brand in A.T1_BRAND_TOKENS:
            j.check(f"answer_brand_{brand.lower()}", affirms(fa, brand), fa)

    elif number == 2:
        j.check("visited_dresses_sale", navigated_path(t, "/c/women-dresses/sale"),
                "Women's Dresses filtered to Sale")
        j.check("answer_count", contains_count(fa, A.T2_COUNT), fa)
        j.check("answer_cheapest_name", affirms(fa, A.T2_CHEAPEST_NAME), fa)
        j.check("answer_brand", affirms_any(fa, ["KARL LAGERFELD", "Karl Lagerfeld"]), fa)
        j.check("answer_current", affirm_money(fa, A.T2_CURRENT), fa)
        j.check("answer_original", affirm_money(fa, A.T2_ORIGINAL), fa)

    elif number == 3:
        j.check("visited_fragrance_chanel", navigated_prefix(t, "/c/beauty-fragrance/brand_chanel")
                or navigated_url_contains(t, "brand=CHANEL") or navigated_url_contains(t, "brand=chanel"),
                "Beauty > Fragrance filtered to CHANEL")
        j.check("visited_coco_pdp", navigated_prefix(t, "/p/chanel-coco-mademoiselle"),
                "COCO MADEMOISELLE product page")
        j.check("answer_count", contains_count(fa, A.T3_COUNT), fa)
        j.check("answer_coco_named", affirms_any(fa, ["COCO MADEMOISELLE", "Coco Mademoiselle"]), fa)
        for size, price in A.T3_COCO_SIZES:
            j.check(f"answer_price_{size.split()[0]}", _coco_size_price(fa, size, price), fa)

    elif number == 4:
        j.check("visited_sweaters_top_rated",
                navigated_query(t, "/c/women-sweaters", orderBy={"topRated", "toprated"}),
                "Women's Sweaters sorted by Top Rated")
        j.check("answer_brand", affirms(fa, A.T4_BRAND), fa)
        j.check("answer_name", affirms(fa, A.T4_NAME), fa)
        j.check("answer_rating", affirm_score(fa, A.T4_RATING), fa)
        j.check("answer_reviews", contains_count(fa, A.T4_REVIEWS), fa)

    elif number == 5:
        j.check("visited_shoes_new", navigated_path(t, "/c/shoes-women-shoes/new-arrivals"),
                "Women's Shoes filtered to New Arrivals")
        j.check("answer_count", contains_count(fa, A.T5_COUNT), fa)
        j.check("answer_cheapest_name", affirms(fa, A.T5_CHEAPEST_NAME), fa)
        j.check("answer_cheapest_price", affirm_money(fa, A.T5_CHEAPEST_PRICE), fa)

    elif number == 6:
        j.check("visited_levis_318", navigated_prefix(t, "/p/levis-318-shaping"),
                "Levi's 318 Shaping jeans product page")
        j.check("answer_item", affirms(fa, A.T6_ITEM), fa)
        j.check("answer_sizes", contains_count(fa, A.T6_SIZES), fa)

    elif number == 7:
        j.check("visited_carter_dress", navigated_prefix(t, "/p/antonio-melani-carter"),
                "Antonio Melani Carter dress product page")
        j.check("answer_color_count", contains_count(fa, len(A.T7_COLORS)), fa)
        for color in A.T7_COLORS:
            j.check(f"answer_color_{color.lower()}", affirms(fa, color), fa)

    elif number == 8:
        j.check("visited_polo", navigated_prefix(t, "/p/polo-ralph-lauren-classic-fit-solid-mesh-polo-shirt"),
                "Polo Ralph Lauren mesh polo product page")
        j.check("answer_rating", affirm_score(fa, A.T8_RATING), fa)
        j.check("answer_reviews", contains_count(fa, A.T8_REVIEWS), fa)
        j.check("answer_five_star", contains_count(fa, A.T8_FIVE_STAR), fa)

    elif number == 9:
        j.check("visited_kaitlin", navigated_prefix(t, "/p/alex-marie-kaitlin"),
                "Alex Marie Kaitlin dress product page")
        j.check("answer_length", affirm_number(fa, A.T9_LENGTH), fa)
        j.check("answer_fabric_poly", affirms_any(fa, ["polyester", "poly"]), fa)
        j.check("answer_fabric_elastane", affirms(fa, "elastane"), fa)

    elif number == 10:
        j.check("visited_timberland", navigated_prefix(t, "/p/timberland-mens-premium-waterproof-boots"),
                "Timberland Premium Waterproof Boots product page")
        j.check("answer_price", affirm_money(fa, A.T10_PRICE), fa)
        j.check("answer_sizes", contains_count(fa, A.T10_SIZES), fa)

    elif number == 11:
        j.check("visited_brahmin", navigated_prefix(t, "/p/brahmin-melbourne-collection-ady"),
                "BRAHMIN Melbourne Ady wallet product page")
        j.check("answer_about_named", affirms_any(fa, ["WHO WE ARE", "About BRAHMIN", "Brahmin"]), fa)
        j.check("answer_sentence", all(affirms(fa, tok) for tok in A.T11_TOKENS), fa)

    elif number == 12:
        j.check("visited_search", navigated_url_contains(t, "search-term"),
                "search results for capri blue")
        j.check("answer_name", affirms(fa, A.T12_NAME), fa)
        j.check("answer_price", affirm_money(fa, A.T12_PRICE), fa)

    elif number == 13:
        j.check("visited_search", navigated_url_contains(t, "search-term"),
                "search results for 511 slim")
        j.check("visited_levis_511", navigated_path(t, "/p/levis-511-slim-fit-all-seasons-tech-jeans/511371759"),
                "a Levi's 511 product page")
        accepted = False
        for cand in A.T13_CANDIDATES[:1]:
            price_ok = _jeans_prices(fa, cand["price"], cand["was"])
            if (all(affirms(fa, tok) for tok in cand["tokens"]) and price_ok
                    and contains_count(fa, cand["sizes"])):
                accepted = True
                j.evidence.append(f"[PASS] answer_candidate: {cand['label']} / "
                                  f"${cand['price']} / {cand['sizes']} sizes")
                break
        j.check("answer_consistent", accepted,
                "All Seasons Tech jeans with current sale price, original price and size count")

    elif number == 14:
        j.check("visited_search", navigated_url_contains(t, "search-term"),
                "search results for kurt geiger")
        j.check("answer_count", contains_count(fa, A.T14_COUNT), fa)
        j.check("answer_cheapest_price", affirm_money(fa, A.T14_CHEAPEST_PRICE), fa)
        j.check("answer_cheapest_name", affirms(fa, A.T14_CHEAPEST_NAME), fa)

    # ---------------- authenticated read-only tasks ----------------
    elif number == 16:
        j.check("visited_bob_orders", navigated_path(t, "/account/orders/4"),
                "bob's delivered order detail")
        j.check("answer_order", affirms(fa, A.T16_ORDER), fa)
        j.check("answer_tracking", affirms(fa, A.T16_TRACKING), fa)
        j.check("answer_carrier", affirms(fa, A.T16_CARRIER), fa)

    elif number == 17:
        j.check("visited_alice_orders", navigated_path(t, "/account/orders/2"),
                "alice's order detail with the Investments pants")
        j.check("answer_order", affirms(fa, A.T17_ORDER), fa)
        ok = (affirms(fa, "September 11") or contains_number(fa, 11)
              and affirms_any(fa, ["September", "Sep", "2026"]))
        j.check("answer_date", ok, fa)
        j.check("answer_items", contains_count(fa, A.T17_ITEMS), fa)

    elif number == 22:
        j.check("visited_registry", navigated_prefix(t, "/registry/114815098"),
                "Sophia Brooks wedding registry page")
        j.check("answer_unpurchased_name", affirms(fa, A.T22_UNPURCHASED), fa)
        j.check("answer_unpurchased_price", affirm_money(fa, A.T22_UNPURCHASED_PRICE), fa)
        j.check("answer_purchased_item", affirms_any(fa, ["COCO MADEMOISELLE", "Coco Mademoiselle"]), fa)

    elif number == 23:
        j.check("visited_registry", navigated_prefix(t, "/registry/114802551"),
                "registry 114802551 page")
        j.check("answer_registrant", affirms(fa, A.T23_NAME), fa)
        j.check("answer_event", affirms_any(fa, ["Baby", "baby"]), fa)
        j.check("answer_items", contains_count(fa, A.T23_ITEMS), fa)

    elif number == 25:
        j.check("visited_stores", navigated_prefix(t, "/stores"),
                "store locator / Dothan store page")
        j.check("answer_store", affirms(fa, A.T25_STORE), fa)
        j.check("answer_address", affirms(fa, A.T25_ADDRESS), fa)
        j.check("answer_city", affirms(fa, "Dothan"), fa)
        j.check("answer_phone", contains_phone(fa, A.T25_PHONE), fa)

    elif number == 26:
        j.check("visited_stores", navigated_prefix(t, "/stores"),
                "store listing / Texas stores page")
        j.check("answer_texas", contains_count(fa, A.T26_TEXAS), fa)
        for name in A.T26_AUSTIN:
            j.check(f"answer_austin_{name.split()[0].lower()}", affirms(fa, name), fa)

    elif number == 27:
        j.check("visited_card_page", navigated_path(t, "/c/DillardsCard"),
                "Dillard's Credit Card page")
        j.check("answer_points", contains_number(fa, A.T27_POINTS), fa)
        j.check("answer_per_dollar", affirms(fa, "2 points per")
                or (contains_number(fa, 2) and affirms_any(fa, ["points per $1", "points per dollar"])), fa)

    # ---------------- stateful tasks ----------------
    elif number == 15:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_confirmation", navigated_prefix(t, "/order-confirmation/"),
                    "order confirmation page")
            orders = new_rows(b, a, "orders")
            j.check("exactly_one_new_order", len(orders) == 1,
                    f"new orders: {[r.get('order_number') for r in orders]}")
            if len(orders) == 1:
                o = orders[0]
                j.check("order_number", o.get("order_number") == A.T15_ORDER,
                        f"order_number: {o.get('order_number')!r}")
                j.check("order_user", o.get("user_id") == 1, f"user_id: {o.get('user_id')}")
                j.check("order_status", o.get("status") == "Processing", o.get("status"))
                j.check("order_payment_kind", o.get("payment_kind") == A.T15_PAYMENT_KIND,
                        o.get("payment_kind"))
                j.check("order_ship_to", A.T15_SHIP_TO in (o.get("ship_to") or ""), o.get("ship_to"))
                j.check("order_total", abs((o.get("total") or 0) - A.T15_TOTAL) < 0.005,
                        f"total: {o.get('total')}")
                j.check("order_subtotal", abs((o.get("subtotal") or 0) - A.T15_SUBTOTAL) < 0.005,
                        f"subtotal: {o.get('subtotal')}")
                items = new_rows(b, a, "order_items")
                j.check("exactly_one_order_item", len(items) == 1,
                        f"new order_items: {[r.get('id') for r in items]}")
                if len(items) == 1:
                    it = items[0]
                    j.check("item_parent_and_quantity", it.get("order_id") == o.get("id")
                            and it.get("quantity") == 1,
                            "one dress belongs to the new order")
                    j.check("item_color", it.get("color") in {"Black", "Sand", "Navy", "Chestnut"},
                            "a real Carter dress color")
                    j.check("item_is_carter_dress", A.T15_DRESS_NAME in (it.get("product_name") or ""),
                            it.get("product_name"))
                    j.check("item_size_8", (it.get("size") or "").strip() == A.T15_SIZE,
                            f"size: {it.get('size')!r}")
                    j.check("item_price", abs((it.get("price") or 0) - A.T15_SUBTOTAL) < 0.005,
                            f"price: {it.get('price')}")
            cart_before_ids = {r["id"] for r in b["cart_items"] if r["user_id"] == 1}
            cart_after_ids = {r["id"] for r in a["cart_items"] if r["user_id"] == 1}
            j.check("bag_emptied_then_bought", cart_after_ids == set(),
                    f"alice's cart rows after: {sorted(cart_after_ids)} "
                    f"(seeded: {sorted(cart_before_ids)})")
            card_b = scalar(b, "card_accounts", id=1)
            card_a = scalar(a, "card_accounts", id=1)
            if card_b is None or card_a is None:
                j.check("card_account_exists", False, "alice's card account missing")
            else:
                j.check("card_balance_before", abs(card_b.get("balance", 0) - A.T15_CARD_BEFORE) < 0.005,
                        card_b.get("balance"))
                j.check("card_balance_after", abs(card_a.get("balance", 0) - A.T15_CARD_AFTER) < 0.005,
                        card_a.get("balance"))
                j.check("card_points_after", card_a.get("points") == A.T15_POINTS_AFTER,
                        card_a.get("points"))
            txns = new_rows(b, a, "card_transactions")
            j.check("one_new_card_txn", len(txns) == 1 and
                    abs((txns[0].get("amount") or 0) - A.T15_TOTAL) < 0.005
                    and txns[0].get("card_account_id") == 1,
                    f"new card_transactions: {[(r.get('description'), r.get('amount')) for r in txns]}")
            ok = preserved(b, a,
                           additions={"orders": [r["id"] for r in new_rows(b, a, "orders")],
                                      "order_items": [r["id"] for r in new_rows(b, a, "order_items")],
                                      "card_transactions": [r["id"] for r in txns]},
                           removals={"cart_items": [r["id"] for r in b["cart_items"] if r["user_id"] == 1]},
                           changes={"card_accounts": {1: {"balance", "points"}}})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_order_number", affirms(fa, A.T15_ORDER), fa)
        j.check("answer_total", affirm_money(fa, A.T15_TOTAL), fa)

    elif number == 18:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_return_form", navigated_prefix(t, "/account/returns/new/"),
                    "return form")
            j.check("visited_returns_page", navigated_path(t, "/account/returns"),
                    "Returns page (credit row)")
            rrs = new_rows(b, a, "return_requests")
            j.check("exactly_one_new_return", len(rrs) == 1,
                    f"new return_requests: {[r.get('id') for r in rrs]}")
            if len(rrs) == 1:
                rr = rrs[0]
                j.check("return_user", rr.get("user_id") == 3, f"user_id: {rr.get('user_id')}")
                item = scalar(a, "order_items", id=rr.get("order_item_id"))
                j.check("return_is_mascara",
                        item is not None and A.T18_ITEM in (item.get("product_name") or ""),
                        item.get("product_name") if item else "order item missing")
                j.check("return_reason", (rr.get("reason") or "") == A.T18_REASON, rr.get("reason"))
                j.check("return_method", (rr.get("method") or "") == A.T18_METHOD, rr.get("method"))
                j.check("return_credit", abs((rr.get("credit_issued") or 0) - A.T18_CREDIT) < 0.005,
                        rr.get("credit_issued"))
            ok = preserved(b, a, additions={"return_requests": [r["id"] for r in rrs]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_credit", affirm_money(fa, A.T18_CREDIT), fa)

    elif number == 19:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_wishlist", navigated_path(t, "/account/wishlist"),
                    "wish list page")
            j.check("visited_bag", navigated_path(t, "/bag"), "bag page (Order Summary)")
            adds = new_rows(b, a, "cart_items")
            j.check("exactly_one_new_cart_row", len(adds) == 1,
                    f"new cart_items: {[r.get('id') for r in adds]}")
            if len(adds) == 1:
                variant = scalar(a, "variants", id=adds[0].get("variant_id"))
                product = scalar(a, "products", id=variant.get("product_id")) if variant else None
                j.check("added_is_capri_blue",
                        product is not None and A.T19_ITEM in (product.get("name") or ""),
                        product.get("name") if product else "product missing")
                j.check("added_price", variant is not None
                        and abs((variant.get("price") or 0) - A.T19_PRICE) < 0.005,
                        variant.get("price") if variant else None)
            ok = preserved(b, a, additions={"cart_items": [r["id"] for r in adds]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_item", affirms(fa, A.T19_ITEM), fa)
        j.check("answer_subtotal", affirm_money(fa, A.T19_SUBTOTAL), fa)

    elif number == 20:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_wishlist", navigated_path(t, "/account/wishlist"),
                    "wish list page")
            gone = removed_rows(b, a, "wishlist_items")
            j.check("exactly_one_wish_removed", len(gone) == 1,
                    f"removed wishlist rows: {[r.get('id') for r in gone]}")
            if len(gone) == 1:
                product = scalar(a, "products", id=gone[0].get("product_id"))
                j.check("removed_is_carter_dress",
                        product is not None and A.T20_NAME in (product.get("name") or ""),
                        product.get("name") if product else "product missing")
            ok = preserved(b, a, removals={"wishlist_items": [r["id"] for r in gone]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_name", affirms(fa, A.T20_NAME), fa)
        j.check("answer_price", affirm_money(fa, A.T20_PRICE), fa)

    elif number == 21:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_wishlist", navigated_path(t, "/account/wishlist"),
                    "wish list page")
            gone = removed_rows(b, a, "wishlist_items")
            j.check("exactly_one_wish_removed", len(gone) == 1,
                    f"removed wishlist rows: {[r.get('id') for r in gone]}")
            if len(gone) == 1:
                product = scalar(a, "products", id=gone[0].get("product_id"))
                j.check("removed_is_brahmin_wallet",
                        product is not None and "BRAHMIN" in (product.get("name") or ""),
                        product.get("name") if product else "product missing")
            ok = preserved(b, a, removals={"wishlist_items": [r["id"] for r in gone]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_left", affirms(fa, A.T21_LEFT), fa)

    elif number == 24:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_registry_create", navigated_prefix(t, "/registry/create")
                    or navigated_url_contains(t, "/registry/G2609"),
                    "registry creation form / created registry page")
            regs = new_rows(b, a, "registries")
            j.check("exactly_one_new_registry", len(regs) == 1,
                    f"new registries: {[r.get('registry_number') for r in regs]}")
            if len(regs) == 1:
                r0 = regs[0]
                j.check("registry_number", r0.get("registry_number") == A.T24_REGISTRY,
                        f"registry_number: {r0.get('registry_number')!r}")
                j.check("registry_user", r0.get("user_id") == 1, f"user_id: {r0.get('user_id')}")
                j.check("registry_kind", r0.get("kind") == A.T24_KIND, r0.get("kind"))
                event = str(r0.get("event_date") or "")
                j.check("registry_event_date", event.startswith(A.T24_EVENT_ISO), event)
                j.check("registry_owner_first", (r0.get("owner_first") or "").lower() == "alice",
                        r0.get("owner_first"))
                j.check("registry_owner_last", (r0.get("owner_last") or "").lower() == "johnson",
                        r0.get("owner_last"))
            ok = preserved(b, a, additions={"registries": [r["id"] for r in regs]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_registry_number", affirms(fa, A.T24_REGISTRY), fa)

    elif number == 28:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_paybill", navigated_path(t, "/account/paybill"),
                    "Pay My Bill page")
            pays = new_rows(b, a, "card_payments")
            j.check("exactly_one_new_payment", len(pays) == 1,
                    f"new card_payments: {[r.get('id') for r in pays]}")
            if len(pays) == 1:
                p = pays[0]
                j.check("payment_card", p.get("card_account_id") == 1,
                        f"card_account_id: {p.get('card_account_id')}")
                j.check("payment_amount", abs((p.get("amount") or 0) - A.T28_AMOUNT) < 0.005,
                        f"amount: {p.get('amount')}")
                j.check("payment_method", (p.get("method") or "") == A.T28_METHOD, p.get("method"))
                j.check("payment_confirmation", p.get("confirmation") == A.T28_CONFIRMATION,
                        p.get("confirmation"))
            card_b = scalar(b, "card_accounts", id=1)
            card_a = scalar(a, "card_accounts", id=1)
            if card_b is None or card_a is None:
                j.check("card_account_exists", False, "alice's card account missing")
            else:
                j.check("balance_before", abs(card_b.get("balance", 0) - A.T28_BEFORE) < 0.005,
                        card_b.get("balance"))
                j.check("balance_after", abs(card_a.get("balance", 0) - A.T28_AFTER) < 0.005,
                        card_a.get("balance"))
            ok = preserved(b, a,
                           additions={"card_payments": [r["id"] for r in pays]},
                           changes={"card_accounts": {1: {"balance"}}})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_confirmation", affirms(fa, A.T28_CONFIRMATION), fa)
        j.check("answer_new_balance", affirm_money(fa, A.T28_AFTER), fa)

    elif number == 29:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_review_form", navigated_url_contains(t, "/reviews/new"),
                    "review form")
            j.check("visited_pdp", navigated_prefix(t, "/p/alex-marie-kaitlin"),
                    "Kaitlin dress product page (updated count)")
            reviews = new_rows(b, a, "reviews")
            j.check("exactly_one_new_review", len(reviews) == 1,
                    f"new reviews: {[r.get('id') for r in reviews]}")
            if len(reviews) == 1:
                rv = reviews[0]
                product = scalar(a, "products", id=rv.get("product_id"))
                j.check("review_product", product is not None
                        and A.T29_PRODUCT in (product.get("name") or ""),
                        product.get("name") if product else "product missing")
                j.check("review_rating", rv.get("rating") == A.T29_RATING, rv.get("rating"))
                j.check("review_title", norm(rv.get("title") or "") == norm(A.T29_TITLE),
                        rv.get("title"))
                j.check("review_body_sentences", sentence_count(rv.get("body") or "") >= 2,
                        f"sentences: {sentence_count(rv.get('body') or '')}")
            prod_b = scalar(b, "products", pid="520620253")
            prod_a = scalar(a, "products", pid="520620253")
            if prod_b is None or prod_a is None:
                j.check("kaitlin_exists", False, "Kaitlin dress product missing")
            else:
                j.check("count_before", prod_b.get("review_count") == A.T29_COUNT_BEFORE,
                        prod_b.get("review_count"))
                j.check("count_after", prod_a.get("review_count") == A.T29_COUNT_AFTER,
                        prod_a.get("review_count"))
                j.check("rating_updated", abs((prod_a.get("rating") or 0) - 4.75) < 0.005,
                        prod_a.get("rating"))
            rb = new_rows(b, a, "rating_breaks")
            j.check("rating_breaks_unchanged", rb == [],
                    f"new rating_breaks rows: {len(rb)}")
            ok = preserved(b, a,
                           additions={"reviews": [r["id"] for r in reviews]},
                           changes={"products": {(prod_a or {"id": None}).get("id"): {"review_count", "rating"}}}
                                    if prod_a else {})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_count", contains_count(fa, A.T29_COUNT_AFTER), fa)

    elif number == 30:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_giftcards", navigated_prefix(t, "/giftcards"),
                    "gift card purchase flow")
            cards = new_rows(b, a, "gift_card_purchases")
            j.check("exactly_one_new_giftcard", len(cards) == 1,
                    f"new gift_card_purchases: {[r.get('id') for r in cards]}")
            if len(cards) == 1:
                g = cards[0]
                j.check("gift_amount", abs((g.get("amount") or 0) - A.T30_AMOUNT) < 0.005,
                        g.get("amount"))
                j.check("gift_recipient", norm(g.get("recipient") or "") == norm(A.T30_RECIPIENT),
                        g.get("recipient"))
                j.check("gift_code", (g.get("code") or "") == A.T30_CODE, g.get("code"))
            ok = preserved(b, a, additions={"gift_card_purchases": [r["id"] for r in cards]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_code", contains_any(fa, ["7334 0922 0100 0001", "7334092201000001"])
                or affirms(fa, "7334 0922 0100 0001"), fa)

    else:
        j.check("unknown_task", False, f"no grading rule for task {number}")

    if emit:
        j.emit()
    return j
