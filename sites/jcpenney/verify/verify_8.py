#!/usr/bin/env python3
"""Verify JCPenney--8."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--8"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_profile", "/account/dashboard/profile")
    judge.check("entered_new_card_number",
                any("4111111111111155" in t for t in
                    (__import__("verify_lib").input_texts(traj))),
                "expected the new card number 4111111111111155 entered on the profile")
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): bob's seeded bag holds the Tree Hut Tropic
    # Glow kit ($23.99 x1), PUMA Active Cargo Pant ($45.00 x2) and St. John's Bay
    # Premium Stretch shirt ($15.39 x1) -> subtotal $129.38; no coupon; subtotal
    # >= 75 so shipping is free; tax $10.67; total $140.05. The new Visa (ending
    # 1155) is saved as the default payment method (the old default Mastercard
    # 5309 flips to non-default) and pays the order.
    judge.check("answer_order_payment",
                contains_all(answer, ["Visa", "1155"]),
                "expected the placed order paid with the Visa ending in 1155")
    judge.check("answer_profile_card_count", contains_count(answer, 2),
                "expected 2 cards on the profile afterwards")
    judge.check("answer_total", contains_amount(answer, 140.05),
                "expected the order total $140.05")
    # --- DB after-state: one payment row added + the old default flipped, one
    # new order + three items, bob's three bag rows removed.
    check_only_tables_changed(judge, initial_db, after_db,
                              ("payment_methods", "orders", "order_items", "cart_items"))
    d_pay = table_delta(initial_db, after_db, "payment_methods")
    d_orders = table_delta(initial_db, after_db, "orders")
    d_items = table_delta(initial_db, after_db, "order_items")
    d_cart = table_delta(initial_db, after_db, "cart_items")
    judge.check("payment_delta_one_added_one_changed",
                len(d_pay["added"]) == 1 and len(d_pay["changed"]) == 1
                and not d_pay["removed"],
                f"payment delta: added={len(d_pay['added'])}, changed={len(d_pay['changed'])}")
    if d_pay["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(payment_methods)")]
        row = dict(zip(cols, d_pay["added"][0]))
        judge.check("added_payment_fields",
                    row.get("user_id") == 2 and row.get("card_type") == "Visa"
                    and row.get("last4") == "1155" and row.get("cardholder") == "Bob Chen"
                    and row.get("exp_month") == 8 and row.get("exp_year") == 2029
                    and row.get("is_default") == 1,
                    f"added payment: {row.get('card_type')} {row.get('last4')}, default={row.get('is_default')}")
    if d_pay["changed"]:
        before_row, after_row = d_pay["changed"][0]
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(payment_methods)")]
        before, after = dict(zip(cols, before_row)), dict(zip(cols, after_row))
        judge.check("old_default_flipped",
                    before.get("user_id") == 2 and before.get("is_default") == 1
                    and after.get("is_default") == 0,
                    f"old default card id={before.get('id')} flipped {before.get('is_default')}->{after.get('is_default')}")
    defaults = [r for r in db_query(
        after_db, "SELECT id, last4 FROM payment_methods WHERE user_id = 2 AND is_default = 1")]
    judge.check("single_new_default", len(defaults) == 1 and defaults[0]["last4"] == "1155",
                f"default payment ids={[d['id'] for d in defaults]}")
    judge.check("orders_delta_one_added", len(d_orders["added"]) == 1 and not d_orders["removed"]
                and not d_orders["changed"],
                f"orders delta: added={len(d_orders['added'])}")
    if d_orders["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(orders)")]
        row = dict(zip(cols, d_orders["added"][0]))
        judge.check("order_row_user_status",
                    row.get("user_id") == 2 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 129.38) < 0.005
                    and abs(row.get("discount", 0) - 0.0) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 10.67) < 0.005
                    and abs(row.get("total", 0) - 140.05) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_shipping_address",
                    row.get("ship_name") == "Bob Chen"
                    and row.get("ship_address") == "2401 Mission St"
                    and row.get("ship_city") == "San Francisco" and row.get("ship_state") == "CA"
                    and row.get("ship_zip") == "94110",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?2", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_three_added",
                len(d_items["added"]) == 3 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        units = sorted((r.get("product_id"), r.get("quantity"), r.get("unit_price")) for r in rows)
        judge.check("order_items_rows",
                    units == sorted([(131, 1, 23.99), (54, 2, 45.00), (45, 1, 15.39)]),
                    f"added order_items (product_id, qty, unit_price)={units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 3 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
