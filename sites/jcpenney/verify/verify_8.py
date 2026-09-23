#!/usr/bin/env python3
"""Verify JCPenney--8."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--8"


from verify_lib import (Judge, changed_tables, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, db_query, final_answer, navigated_to_path, re,
                        run_verifier, table_delta, TABLES)

TASK_ID = "JCPenney--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(__import__("verify_lib").normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in __import__("verify_lib").site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB, alice's bag subtotal $68.99 + SAVE30 = 30% off):
    # discount $20.70, shipping $8.95. The review step applies the estimated tax to
    # the discounted subtotal (F3 fix, matching the bag page's ?code= convention), so
    # the frozen expectation is tax $3.98 and total $61.22. The order number is
    # runtime-generated (JCP + HHMMSS + 001) so it is matched by pattern.
    import re as _re
    judge.check("answer_order_number_pattern",
                bool(_re.search(r"JCP\d{6}00?1", answer.replace(" ", ""))),
                "expected the new order number (JCP + 6 digits + 001)")
    judge.check("answer_discount", contains_amount(answer, 20.70),
                "expected the SAVE30 discount $20.70")
    judge.check("answer_total", contains_amount(answer, 61.22),
                "expected the order total $61.22")
    # --- DB after-state: one new order + two new order_items, alice's two bag rows
    # removed, everything else row-identical.
    check_only_tables_changed(judge, initial_db, after_db,
                              ("orders", "order_items", "cart_items"))
    d_orders = table_delta(initial_db, after_db, "orders")
    d_items = table_delta(initial_db, after_db, "order_items")
    d_cart = table_delta(initial_db, after_db, "cart_items")
    judge.check("orders_delta_one_added", len(d_orders["added"]) == 1 and not d_orders["removed"]
                and not d_orders["changed"],
                f"orders delta: added={len(d_orders['added'])}, removed={len(d_orders['removed'])}, "
                f"changed={len(d_orders['changed'])}")
    if d_orders["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(orders)")]
        row = dict(zip(cols, d_orders["added"][0]))
        judge.check("order_row_user_status", row.get("user_id") == 1 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "SAVE30",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 68.99) < 0.005
                    and abs(row.get("discount", 0) - 20.70) < 0.005
                    and abs(row.get("shipping", 0) - 8.95) < 0.005
                    and abs(row.get("tax", 0) - 3.98) < 0.005
                    and abs(row.get("total", 0) - 61.22) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, total={row.get('total')}")
        judge.check("order_row_shipping_address",
                    row.get("ship_name") == "Alice Johnson"
                    and row.get("ship_address") == "1460 Alderwood Mall Blvd"
                    and row.get("ship_city") == "Lynnwood" and row.get("ship_state") == "WA"
                    and row.get("ship_zip") == "98037",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}")
        judge.check("order_row_payment", row.get("payment_type") == "Visa" and row.get("payment_last4") == "4242",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?1", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_two_added", len(d_items["added"]) == 2 and not d_items["removed"]
                and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    added_units = sorted((r[2], r[8]) for r in d_items["added"]) if d_items["added"] else []
    judge.check("order_items_rows",
                added_units == sorted([(61, 31.49), (53, 37.50)]),
                f"added order_items (product_id, unit_price)={added_units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 2 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
