#!/usr/bin/env python3
"""Verify JCPenney--7."""

from review_common import amount
from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--7"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    SHEET1000 = "/p/liz-claiborne-luxury-performance-1000tc-sheet-set/ppr5008236237"
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_coupons", "/m/jcpenney-coupons")
    judge.check("visited_bedding_brand_filtered",
                navigated_listing_with_filter(traj, "/g/home-store/all-bedding",
                                              "brand", "liz claiborne"),
                "required: /g/home-store/all-bedding with brand=liz claiborne")
    check_visited_path(judge, traj, "visited_sheet_pdp", SHEET1000)
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # GOSHOP15 is the advertised fixed $10 discount on a purchase of $50+.
    # Carol's dress and two sheet sets total $162.37 before the discount;
    # tax is $12.57 and the final order is $164.94 with free standard shipping.
    judge.check("answer_advertised_terms",
                bool(_re.search(amount(10), answer)) and bool(_re.search(amount(50), answer)),
                "expected the advertised $10-off-$50 terms restated")
    judge.check("answer_applied_discount", contains_amount(answer, 10.00),
                "expected the applied GOSHOP15 discount $10.00")
    judge.check("answer_matches_offer", contains_any(answer,["matches", "matched", "same as", "consistent"]), "the applied $10 discount matches the offer")
    judge.check("answer_total", contains_amount(answer, 164.94),
                "expected the order total $164.94")
    # --- DB after-state: one new order + its items, carol's one bag row removed.
    check_only_tables_changed(judge, initial_db, after_db,
                              ("orders", "order_items", "cart_items"))
    d_orders = table_delta(initial_db, after_db, "orders")
    d_items = table_delta(initial_db, after_db, "order_items")
    d_cart = table_delta(initial_db, after_db, "cart_items")
    judge.check("orders_delta_one_added", len(d_orders["added"]) == 1 and not d_orders["removed"]
                and not d_orders["changed"],
                f"orders delta: added={len(d_orders['added'])}")
    if d_orders["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(orders)")]
        row = dict(zip(cols, d_orders["added"][0]))
        judge.check("order_row_user_status",
                    row.get("user_id") == 3 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "GOSHOP15",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 162.37) < 0.005
                    and abs(row.get("discount", 0) - 10.00) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 12.57) < 0.005
                    and abs(row.get("total", 0) - 164.94) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_payment",
                    row.get("payment_type") == "American Express" and row.get("payment_last4") == "1005",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?3", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_sheet_quantity",
                len(d_items["added"]) in (2, 3) and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        dress = [r for r in rows if r.get("product_id") == 3]
        sheets = [r for r in rows if r.get("product_id") == 74]
        judge.check("order_items_rows",
                    len(dress) == 1 and dress[0].get("quantity") == 1
                    and abs(dress[0].get("unit_price", 0) - 78.39) < 0.005
                    and sheets and sum(r.get("quantity", 0) for r in sheets) == 2
                    and all(abs(r.get("unit_price", 0) - 41.99) < 0.005 for r in sheets),
                    f"order items: dress={dress!r}, sheets={sheets!r}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 1 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
