"""Shared deterministic BIRKENSTOCK task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / money / tokens,
     negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows/fields and preserve the rest
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, one, preserved, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_pdp,
    contains_count, contains_money, affirm_number, affirm_money, affirm_score,
    affirms, affirms_any, contains_any, contains_number, norm, final_answer,
    step_text, shot_at,
)
import answers

# ---------------------------------------------------------------- ground truth
# T0: search "Arizona EVA" — cheapest adult (non-kids) colorways, 5-way price tie.
T0_TIE = {
    "arizona-eva-eva-0-eva-u_11562": ("Arizona Essentials", "Papaya"),
    "arizona-eva-eva-0-eva-u_2138": ("Arizona Essentials", "Faded Lime"),
    "arizonaessentials-tothebeachmetallic-eva-0-eva-u_11689": ("Arizona Essentials", "Fondant Pink"),
    "arizonaessentials-tothebeachmetallic-eva-0-eva-u_1594": ("Arizona Essentials", "Active Red"),
    "arizonaeva-eva-eva-0-eva-u_1942": ("Arizona Essentials", "Glamour Gold"),
}
# T5: Water-friendly (EVA) category cheapest — 8-way price tie at $32.47.
T5_TIE = {
    "arizona-eva-eva-0-eva-u_11562": ("Arizona Essentials", "Papaya"),
    "arizona-eva-eva-0-eva-u_2138": ("Arizona Essentials", "Faded Lime"),
    "arizonaessentials-tothebeachmetallic-eva-0-eva-u_11689": ("Arizona Essentials", "Fondant Pink"),
    "arizonaessentials-tothebeachmetallic-eva-0-eva-u_1594": ("Arizona Essentials", "Active Red"),
    "arizonaeva-eva-eva-0-eva-u_1942": ("Arizona Essentials", "Glamour Gold"),
    "gizeh-eva-eva-0-eva-u_11562": ("Gizeh Essentials", "Papaya"),
    "gizeh-eva-eva-0-eva-u_1989": ("Gizeh Essentials", "Khaki"),
    "gizeh-eva-eva-0-eva-u_2138": ("Gizeh Essentials", "Faded Lime"),
}
# T4: Sale category, Upper material EVA — every product carrying the max -35% badge.
T4_35 = [
    ("Arizona Essentials", "Glamour Gold"),
    ("Arizona Stealth Buckle", "Surf Green"),
    ("Gizeh Essentials", "Papaya"),
    ("Gizeh Essentials", "Khaki"),
    ("Gizeh Essentials", "Faded Lime"),
]
# T10: Arizona Big Buckle Oiled Leather colorway pids + swatch names.
T10_PIDS = {
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_10556": "Olive Green",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_11969": "Pure Sage",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_11984": "Basalt Gray",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_1770": "Black",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_5326": "Habana",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_7888": "Tobacco Brown",
    "arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_9798": "Cognac",
}
T10_COLORS = ["Olive Green", "Pure Sage", "Basalt Gray", "Black", "Habana", "Tobacco Brown", "Cognac"]

# PDP anchors
P_BOSTON_OILED_BLACK = "boston-core-oiledleather-0-eva-u_449"
P_BOSTON_SF_OYSTER = "boston-suede-suedeleather-softfootbed-eva-u_12168"
P_MADRID_BIRKO_BLACK = "madrid-core-birkoflor-0-eva-u_79"
P_GIZEH_OILED_BLACK = "gizeh-core-oiledleather-0-eva-u_449"
P_BOSTON_SF_TAUPE = "boston-suede-suedeleather-softfootbed-eva-u_46"
P_KIT = "3stepfoot-careessentials-footcarekit-0-0-u_11838"
P_MAYARI_BIRKO_BLACK = "mayari-core-birkoflor-0-eva-u_79"
P_ARIZONA_BIRKO_SILVER = "arizona-core-birkoflor-0-eva-w_109"
P_ARIZONA_BB_NUBUCK_PEPPER = "arizonabigbuckle-nubuk-nubuckleather-0-eva-w_12349"
P_GIZEH_BIRKO_BLACK = "gizeh-core-birkoflor-0-eva-u_79"

ALICE, BOB, CAROL, DAVID = "alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"
DEMO_PASSWORD = "TestPass123!"

# Seeded cart math (from the frozen seed; also asserted in test_verifiers.py)
T14_SUBTOTAL = 380.32   # 29.95 + 2x116.21 + 117.95
T15_SUBTOTAL = 962.29   # 210.00 + 2x113.72 + 174.95 + 2x174.95
T18_SUBTOTAL, T18_TAX, T18_TOTAL = 372.37, 33.05, 405.42  # + Gizeh 110.00
T18_ORDER_NO = "US-20260921-00007"
T21_TO_PREMIUM = 145.30  # 700.00 - 554.70

# Stores (frozen seed; the degenerate upstream address "0" is not a street address)
AUSTIN_STREETS = (
    "2901 S Capital of Texas Hwy", "1007 South Congress Ave", "1011 W Anderson Lane",
    "3211 Feathergrass Ct", "2901 N Capitol of Texas Hwy", "11700 Rock Rose Ave Suite 166",
    "2438 W Anderson Ln", "9901 N Capital of Texas Hwy Ste 120", "4615 N Lamar Ste 305",
    "7434 North Lamar Blvd", "3200 Palm Way", "9901 N Capitol of Texas Hwy",
    "9901 N Capital of Texas Highway", "13359 UDS HWY 183 N Ste 402",
    "1210 South Congress Ave", "1423 South Congress Ave", "3220 Amy Donovan Plaza",
    "2901 S. Capital of Texas Highway", "15500 SH-71", "4477 S Lamar Blvd",
    "1014 N Lamar Blvd", "2901 S Capital of Texas Hwy, Space k08A", "221 W 2nd St",
    "3210 Kramer Lane", "701 S Capital Of Texas Hwy",
)
BROOKLYN_STREETS = (
    "70 N 6th St", "1924 Church Ave", "77 Atlantic Ave", "233 Prospect Park W",
    "484 5th Ave", "5100 Kings Plaza", "1114 Avenue J", "4715 13th Avenue",
    "1267 Broadway", "425 Fulton Street", "811 Van Siclen Ave", "517 Park Ave",
    "1217 Bedford Av", "316 7th Ave", "2013 86th St", "220 5th Ave", "888 Manhattan Ave",
    "141 Smith St", "230 7th Ave", "133 N 7th St", "185 Smith St", "349 Court Street",
    "774 Bedford Ave", "466 Bergen St", "160 Gravesend Neck Rd", "452 Knickerbocker Ave",
    "4520 18 Avenue", "1055 Liberty Avenue", "109 S 6th Street 2nd FL", "197 Bedford Ave",
    "233 Flatbush Ave", "85 North 3rd Street", "3115 Coney Island Ave", "5402 5th Ave",
)

READ_ONLY = set(range(0, 14)) | set(range(19, 30))   # every task except 14-18


def money_list(text, value):
    return contains_money(text, value)


def grade(number):
    args = parse_args()
    j = Judge(f"Birkenstock--{number}")
    t = load_run(args.run_dir)
    fa = final_answer(t)
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    b, a = rows(init_db), rows(after_db)
    j.bind_run(t, require_answer=True)
    from reviewed import check
    check(j, number, t, b, a)

    if number in READ_ONLY:
        changed = tables_unchanged(init_db, after_db)
        if changed is None:
            j.check("db_unchanged", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("db_unchanged", changed == [], f"changed tables: {changed}" if changed else "all tables byte-identical")

    # ---------------- per-task checks ----------------
    if number == 0:
        j.check("search_page_visited", navigated_query(t, "/us/search/", q={"arizona eva", "arizona+eva"}),
                "searched 'arizona eva' on the mirror")
        opened = navigated_pdp(t, T0_TIE)
        j.check("pdp_cheapest_adult_visited", opened, f"opened a PDP of one of the tied cheapest adult colorways {sorted(T0_TIE)}")
        j.check("answer_name", affirms(fa, "arizona essentials"), fa)
        j.check("answer_price", affirm_money(fa, 32.47), fa)
        if opened:
            visited = [pid for pid in T0_TIE if navigated_pdp(t, {pid})]
            colors = {T0_TIE[pid][1] for pid in visited}
            j.check("answer_color_matches_pdp", affirms_any(fa, list(colors)), f"opened colors {sorted(colors)}")
        else:
            j.check("answer_color_matches_pdp", False, "no tied PDP opened")
        j.check("not_kids_result",
                not affirms(re.sub(r"\bnon-kids\b|\(non-kids\)", "", fa, flags=re.I), "kids"),
                "adult (non-kids) result reported")

    elif number == 1:
        j.check("plp_visited_with_filter_sort",
                navigated_query(t, "/us/women/sandals/", color="Black", sort="price-asc"),
                "women's sandals, color=Black, sort=price-asc")
        j.check("answer_name", affirms(fa, "siena rivet"), fa)
        j.check("answer_price", affirm_money(fa, 116.21), fa)

    elif number == 2:
        j.check("plp_visited_with_price_filter",
                navigated_query(t, "/us/men/shoes/clogs/", max_price="150"),
                "men's clogs with max_price=150")
        j.check("answer_count", contains_count(fa, 64), fa)
        j.check("answer_name", affirms(fa, "amsterdam wrapped"), fa)
        j.check("answer_price", affirm_money(fa, 134.95), fa)

    elif number == 3:
        j.check("plp_visited", navigated_path(t, "/us/kids/boys-sandals/"), "boys sandals PLP")
        j.check("answer_count", contains_count(fa, 35), fa)
        j.check("answer_name", affirms(fa, "gizeh essentials kids"), fa)
        j.check("answer_price", affirm_money(fa, 22.72), fa)

    elif number == 4:
        j.check("plp_visited_with_material_filter",
                navigated_query(t, "/us/sale/", material="EVA"),
                "sale PLP with material=EVA")
        j.check("answer_max_discount", answers.percent_value(fa, 35), fa)
        j.check("answer_product_with_it",
                any(affirms(fa, m) and (affirms(fa, c) or norm(c) in norm(fa)) for m, c in T4_35),
                f"one of {T4_35}")

    elif number == 5:
        j.check("plp_visited", navigated_path(t, "/us/eva-sandals/"), "water-friendly (EVA) PLP")
        j.check("answer_price", affirm_money(fa, 32.47), fa)
        ok_pair = any(affirms(fa, m) and affirms(fa, c) for m, c in T5_TIE.values())
        j.check("answer_name_and_color", ok_pair, f"one of {sorted(set(T5_TIE.values()))}")

    elif number == 6:
        j.check("pdp_visited", navigated_pdp(t, P_BOSTON_OILED_BLACK), "Boston Oiled Leather Black PDP")
        j.check("answer_price", affirm_money(fa, 154.95), fa)
        j.check("answer_rating", affirm_score(fa, 4.8), fa)
        j.check("answer_reviews", contains_count(fa, 177), fa)

    elif number == 7:
        j.check("search_page_visited", navigated_query(t, "/us/search/", q={"boston soft footbed", "boston+soft+footbed"}),
                "searched 'boston soft footbed'")
        j.check("pdp_visited", navigated_pdp(t, P_BOSTON_SF_OYSTER), "Boston Soft Footbed Oyster Tonal PDP")
        j.check("answer_item_number", affirms(fa, "0560771") and affirms(fa, "0560773"), fa)
        j.check("answer_rating", affirm_score(fa, 4.8), fa)

    elif number == 8:
        j.check("pdp_visited", navigated_pdp(t, P_MADRID_BIRKO_BLACK), "Madrid Birko-Flor Black PDP")
        j.check("answer_footbed_material", affirms(fa, "cork"), fa)
        j.check("page_evidence_material_section",
                contains_any(step_text(t), ["Footbed material", "footbed material"]),
                "Material section rendered on the PDP")

    elif number == 9:
        j.check("pdp_visited", navigated_pdp(t, P_GIZEH_OILED_BLACK), "Gizeh Oiled Leather Black PDP")
        j.check("answer_eu_size", contains_count(fa, 40), fa)
        j.check("answer_price", affirm_money(fa, 139.95), fa)

    elif number == 10:
        j.check("pdp_visited", navigated_pdp(t, set(T10_PIDS)), "Arizona Big Buckle Oiled Leather PDP")
        j.check("answer_color_count", contains_count(fa, 7), fa)
        missing = [c for c in T10_COLORS if not affirms(fa, c)]
        j.check("answer_all_colors", not missing, f"missing: {missing}" if missing else "all 7 swatch names")

    elif number == 11:
        j.check("pdp_visited", navigated_pdp(t, P_BOSTON_SF_TAUPE), "Boston Soft Footbed Suede Taupe PDP")
        j.check("answer_price", affirm_money(fa, 169.95), fa)
        j.check("answer_afterpay", affirm_money(fa, 14.71), fa)
        j.check("answer_reviews", contains_count(fa, 407), fa)

    elif number == 12:
        j.check("pdp_visited", navigated_pdp(t, P_KIT), "3-Step Foot Care Kit PDP")
        j.check("answer_price", affirm_money(fa, 29.95), fa)
        j.check("answer_badge", affirms(fa, "bestseller"), fa)
        j.check("answer_set_contents",
                affirms(fa, "exfoliating foot scrub") and affirms(fa, "nourishing foot balm")
                and affirms_any(fa, ["relief lotion", "relief lotion tired leg"]),
                fa)

    elif number == 13:
        j.check("pdp_visited", navigated_pdp(t, P_MAYARI_BIRKO_BLACK), "Mayari Birko-Flor Black PDP")
        j.check("answer_price", affirm_money(fa, 112.95), fa)
        j.check("answer_reviews", contains_count(fa, 66), fa)

    elif number == 14:
        _cart_task(j, t, a, b, fa,
                   email=ALICE, pid=P_ARIZONA_BIRKO_SILVER, size="8-8.5",
                   width="Regular/Wide", qty=1, subtotal=T14_SUBTOTAL, shipping_free=True)

    elif number == 15:
        _cart_task(j, t, a, b, fa,
                   email=BOB, pid=P_ARIZONA_BB_NUBUCK_PEPPER, size="9-9.5",
                   width="Regular/Wide", qty=2, subtotal=T15_SUBTOTAL, shipping_free=True)

    elif number == 16:
        _profile_task(j, t, a, b, fa)

    elif number == 17:
        _payment_task(j, t, a, b, fa)

    elif number == 18:
        _checkout_task(j, t, a, b, fa)

    elif number == 19:
        j.check("login_visited", navigated_path(t, "/us/login/"), "logged in as alice")
        j.check("account_visited", navigated_path(t, "/us/account/") or navigated_path(t, "/us/orders/"),
                "account/orders page")
        j.check("answer_order_no", affirms(fa, "us-20260909-00001"), fa)
        j.check("answer_status", affirms(fa, "delivered"), fa)
        j.check("answer_tracking", affirms(fa, "1z900000000birk100"), fa)

    elif number == 20:
        j.check("order_status_visited", navigated_path(t, "/us/order-status/")
                or navigated_path(t, "/us/track-order/"), "order status page")
        j.check("answer_status", affirms(fa, "shipped"), fa)
        j.check("answer_shipping_method", affirms(fa, "ground shipping"), fa)
        j.check("answer_tracking", affirms(fa, "1z900012352birk101"), fa)

    elif number == 21:
        j.check("login_visited", navigated_path(t, "/us/login/"), "logged in as david")
        j.check("account_visited", navigated_path(t, "/us/account/"), "account page with VIP box")
        j.check("answer_tier", affirms(fa, "classic"), fa)
        j.check("answer_points", contains_count(fa, 579), fa)
        j.check("answer_to_premium", contains_money(fa, T21_TO_PREMIUM) or affirm_number(fa, 145), fa)

    elif number == 22:
        j.check("vip_page_visited", navigated_path(t, "/us/birkenstock-vip/") or navigated_path(t, "/us/vip-access/"),
                "VIP page")
        j.check("answer_spend_range", affirm_number(fa, 200) and affirm_number(fa, 699), fa)
        benefits = answers.classic_benefits(fa)
        j.check("answer_two_benefits", benefits >= 2, f"distinct CLASSIC benefits: {benefits}")

    elif number == 23:
        j.check("vip_page_visited", navigated_path(t, "/us/birkenstock-vip/") or navigated_path(t, "/us/vip-access/"),
                "VIP page")
        j.check("answer_review_points", answers.review_points_25(fa), fa)
        j.check("answer_redeem", contains_count(fa, 300) and affirm_number(fa, 10), fa)

    elif number == 24:
        j.check("locator_visited_austin", navigated_query(t, "/us/storelocator/", q={"Austin", "austin"}),
                "store locator searched for Austin")
        j.check("answer_count", contains_count(fa, 25), fa)
        j.check("answer_address", any(affirms(fa, s) for s in AUSTIN_STREETS), fa)

    elif number == 25:
        j.check("locator_visited_brooklyn", navigated_query(t, "/us/storelocator/", q={"Brooklyn", "brooklyn"}),
                "store locator searched for Brooklyn")
        j.check("answer_count", contains_count(fa, 34), fa)
        j.check("answer_address", any(affirms(fa, s) for s in BROOKLYN_STREETS), fa)

    elif number == 26:
        j.check("policy_visited", navigated_path(t, "/us/policies/returns/"), "return policy page")
        j.check("answer_window_days", contains_count(fa, 30), fa)
        j.check("answer_final_sale_rule", answers.sale_items_final(fa), fa)

    elif number == 27:
        j.check("policy_visited", navigated_path(t, "/us/policies/shipping/"), "shipping policy page")
        j.check("answer_ground_days", answers.ground_days_2_to_5(fa), fa)
        j.check("answer_cutoff", answers.two_day_cutoff(fa), fa)

    elif number == 28:
        j.check("service_visited", navigated_path(t, "/us/service/") or navigated_path(t, "/us/contact-customer-service/"),
                "customer service page")
        j.check("answer_phone", answers.toll_free_phone(fa), fa)
        j.check("answer_hours", answers.support_hours(fa), fa)

    elif number == 29:
        j.check("guide_visited", navigated_path(t, "/us/service/fitting-guide/"), "fit and size guide")
        j.check("answer_men_43", answers.men_size_binding(fa, "10-10.5", 43), fa)
        j.check("answer_women_38", answers.women_size_binding(fa, "7-7.5", 38), fa)

    else:
        j.check("task_exists", False, f"no grading logic for task {number}")

    j.emit()


# ---------------------------------------------------------------- stateful helpers
def _cart_task(j, t, a, b, fa, email, pid, size, width, qty, subtotal, shipping_free):
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("login_visited", navigated_path(t, "/us/login/"), f"logged in as {email}")
    j.check("pdp_visited", navigated_pdp(t, pid), "product page for the requested colorway")
    j.check("cart_visited", navigated_path(t, "/us/cart/"), "cart page with order summary")
    user = one(b, "users", email=email)
    product = one(b, "products", pid=pid)
    j.check("cart_row_created",
            any(r["user_id"] == user["id"] and r["product_id"] == product["id"]
                and r["size"] == size and r["width"] == width and r["quantity"] == qty
                for r in a["cart_items"]),
            f"cart row: product={pid} size={size} width={width} qty={qty}")
    existed = any(r["user_id"] == user["id"] and r["product_id"] == product["id"] for r in b["cart_items"])
    j.check("only_requested_cart_changes",
            preserved(b, a, changes={"cart_items": {r["id"]: {"quantity"} for r in a["cart_items"]
                                                   if r["user_id"] == user["id"] and r["product_id"] == product["id"]}},
                      additions={} if existed else {"cart_items": [r["id"] for r in a["cart_items"]
                                                                   if r["user_id"] == user["id"] and r["product_id"] == product["id"]]}),
            "other cart rows, users, orders unchanged")
    j.check("answer_subtotal", affirm_money(fa, subtotal), fa)
    if shipping_free:
        j.check("answer_shipping_free", affirms_any(fa, ["free", "$0.00", "0.00", "no charge"]), fa)


def _profile_task(j, t, a, b, fa):
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("login_visited", navigated_path(t, "/us/login/"), "logged in as carol")
    j.check("profile_visited", navigated_path(t, "/us/account/profile"), "profile page")
    user = one(b, "users", email=CAROL)
    row = one(a, "users", id=user["id"])
    j.check("city_updated", row["city"] == "Denver", f"city={row['city']!r}")
    j.check("state_updated", row["state"] == "CO", f"state={row['state']!r}")
    j.check("zip_updated", row["zip_code"] == "80202", f"zip={row['zip_code']!r}")
    j.check("street_preserved", row["address1"] == "733 Hayes St", f"address1={row['address1']!r}")
    j.check("other_state_preserved", preserved(b, a, changes={"users": {user["id"]: {"city", "state", "zip_code"}}}),
            "only the requested profile fields changed")
    j.check("answer_full_address",
            affirms(fa, "733 hayes st") and affirms(fa, "denver") and affirms(fa, "co")
            and affirms(fa, "80202"), fa)


def _payment_task(j, t, a, b, fa):
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("login_visited", navigated_path(t, "/us/login/"), "logged in as david")
    j.check("payment_page_visited", navigated_path(t, "/us/account/payment"), "payment methods page")
    user = one(b, "users", email=DAVID)
    new = [r for r in a["payment_methods"] if r["user_id"] == user["id"]
           and r["label"] == "Mastercard" and r["last_four"] == "8888"]
    j.check("card_row_created", len(new) == 1, f"new card rows: {new}")
    j.check("only_requested_payment_changes",
            preserved(b, a, additions={"payment_methods": [r["id"] for r in new]}),
            "existing cards and all other tables unchanged")
    j.check("answer_label", affirms(fa, "mastercard"), fa)
    j.check("answer_last_four", affirm_number(fa, 8888), fa)


def _checkout_task(j, t, a, b, fa):
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("login_visited", navigated_path(t, "/us/login/"), "logged in as alice")
    j.check("pdp_visited", navigated_pdp(t, P_GIZEH_BIRKO_BLACK), "Gizeh Birko-Flor Black PDP")
    j.check("checkout_visited", navigated_path(t, "/us/checkout/"), "checkout flow")
    user = one(b, "users", email=ALICE)
    new = new_rows(b, a, "orders")
    j.check("one_new_order", len(new) == 1, f"new orders: {len(new)}")
    if len(new) == 1:
        order = new[0]
        expected = {
            "order_no": T18_ORDER_NO, "user_id": user["id"], "status": "Processing",
            "payment_label": "Visa", "payment_last_four": "1111",
            "shipping_method": "Ground Shipping", "shipping_cost": 0.0,
            "subtotal": T18_SUBTOTAL, "tax": T18_TAX, "total": T18_TOTAL,
            "points_earned": 372, "email": ALICE,
        }
        mismatches = {k: order[k] for k, v in expected.items() if order[k] != v}
        j.check("order_fields", not mismatches, f"mismatched: {mismatches}" if mismatches else str(expected))
        j.check("order_items", len([r for r in a["order_items"] if r["order_id"] == order["id"]]) == 3,
                "order carries the 3 cart items (kit, Arizona Soft Footbed x2, Gizeh)")
        j.check("order_detail_visited", navigated_path(t, f"/us/orders/{T18_ORDER_NO}/"),
                "order confirmation page")
        j.check("new_card_saved", any(r["user_id"] == user["id"] and r["label"] == "Visa"
                                     and r["last_four"] == "1111" for r in a["payment_methods"]),
                "new Visa card row")
        after_user = one(a, "users", id=user["id"])
        j.check("points_accrued", after_user["vip_points"] == user["vip_points"] + 372,
                f"vip_points {user['vip_points']} -> {after_user['vip_points']}")
        j.check("spend_accrued", abs(after_user["lifetime_spend"] - (user["lifetime_spend"] + T18_SUBTOTAL)) < 0.005,
                f"lifetime_spend {user['lifetime_spend']} -> {after_user['lifetime_spend']}")
        j.check("cart_emptied", not any(r["user_id"] == user["id"] for r in a["cart_items"]),
                "alice's cart emptied after purchase")
        removed = [r["id"] for r in b["cart_items"] if r["user_id"] == user["id"]]
        j.check("only_requested_checkout_changes",
                preserved(b, a,
                          changes={"users": {user["id"]: {"vip_points", "lifetime_spend"}}},
                          additions={"orders": [order["id"]],
                                     "order_items": [r["id"] for r in a["order_items"] if r["order_id"] == order["id"]],
                                     "payment_methods": [r["id"] for r in a["payment_methods"]
                                                         if r["user_id"] == user["id"] and r["label"] == "Visa"
                                                         and r["last_four"] == "1111"]},
                          removals={"cart_items": removed}),
                "no unrelated table/row changes")
    j.check("answer_order_no", affirms(fa, T18_ORDER_NO.lower()), fa)
    j.check("answer_total", affirm_money(fa, T18_TOTAL), fa)
