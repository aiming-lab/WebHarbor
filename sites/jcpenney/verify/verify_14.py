#!/usr/bin/env python3
"""Verify JCPenney--14."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--14"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    MOCKNECK = "/p/st-john-s-bay-womens-mock-neck-long-sleeve-t-shirt/ppr5008659536"
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # NOTE: the quantity-update and line-removal are enforced by the DB contract
    # below (order_items must carry the flannel at qty 3 and no PUMA row) - the
    # bag page qty/remove forms submit via JS, so their action URLs never appear
    # in a real trajectory page URL list.
    judge.check("visited_mockneck_search",
                navigated_search(traj, "mock neck"),
                "required: the site search for the mock neck t-shirt")
    check_visited_path(judge, traj, "visited_mockneck_pdp", MOCKNECK)
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): alice's bag holds the Arizona hooded flannel
    # shirt ($31.49) and PUMA sweatpants ($37.50). After qty 3 on the flannel
    # ($94.47), removing the PUMA line, and adding one St. John's Bay mock neck
    # t-shirt ($11.89), the pre-order bag is flannel x3 + tee = subtotal $106.36;
    # no coupon; subtotal >= 75 so shipping is free; tax $8.77; total $115.13,
    # paid with the default Visa ending 4242.
    judge.check("answer_flannel_line",
                contains_all(answer, ["31.49", "94.47"]),
                "expected the flannel line ($31.49 x3 = $94.47) in the pre-order bag")
    judge.check("answer_mockneck_line",
                contains_all(answer, ["Mock Neck", "11.89"]),
                "expected the mock neck t-shirt at $11.89 in the pre-order bag")
    judge.check("answer_subtotal", contains_amount(answer, 106.36),
                "expected the pre-order bag subtotal $106.36")
    judge.check("answer_total", contains_amount(answer, 115.13),
                "expected the final order total $115.13")
    # --- DB after-state: one new order + two items (flannel x3, mock neck tee),
    # alice's two bag rows removed (the in-run tee row is born and deleted inside
    # the window).
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
                    row.get("user_id") == 1 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 106.36) < 0.005
                    and abs(row.get("discount", 0) - 0.0) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 8.77) < 0.005
                    and abs(row.get("total", 0) - 115.13) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_shipping_address",
                    row.get("ship_name") == "Alice Johnson"
                    and row.get("ship_address") == "1460 Alderwood Mall Blvd"
                    and row.get("ship_city") == "Lynnwood" and row.get("ship_state") == "WA"
                    and row.get("ship_zip") == "98037",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}")
        judge.check("order_row_payment",
                    row.get("payment_type") == "Visa" and row.get("payment_last4") == "4242",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?1", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_two_added",
                len(d_items["added"]) == 2 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        units = sorted((r.get("product_id"), r.get("quantity"), r.get("unit_price")) for r in rows)
        judge.check("order_items_rows",
                    units == sorted([(61, 3, 31.49), (11, 1, 11.89)]),
                    f"added order_items (product_id, qty, unit_price)={units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 2 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
