#!/usr/bin/env python3
"""Verify JCPenney--3."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--3"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    HOPE = "/p/st-john-s-bay-womens-hope-stacked-heel-booties/ppr5008660553"
    KINNEL = "/p/st-john-s-bay-womens-kinnel-flat-heel-booties/ppr5008660563"
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("visited_boots_search_sorted",
                navigated_search_sorted(traj, "boots", "price_low"),
                "required: /s/boots with sortBy=price_low")
    judge.check("visited_cheapest_booties_pdp",
                any(normalized_url_path(u) in (HOPE, KINNEL) for u in site_urls(traj)),
                "required: the cheapest pair's product page (Hope or Kinnel booties, $27.99 tie)")
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): cheapest boots = St. John's Bay Hope Stacked
    # Heel Booties at $27.99 (tie with the Kinnel booties; the low-to-high sort
    # lists Hope first). Guest bag merges with alice's seeded bag (Arizona flannel
    # $31.49 + PUMA jogger $37.50) -> subtotal $96.98; SAVE30 (30%) = $29.09;
    # subtotal >= $75 so shipping is free; tax on the discounted subtotal $5.60;
    # total $73.49, paid with the default Visa ending 4242.
    judge.check("answer_pair_bought",
                (contains_all(answer, ["Hope Stacked Heel Booties", "27.99"])
                 or contains_all(answer, ["Kinnel Flat Heel Booties", "27.99"])),
                "expected the bought pair (Hope or Kinnel booties) at $27.99")
    judge.check("answer_order_number_pattern",
                bool(_re.search(r"JCP\d{6}00?1", answer.replace(" ", ""))),
                "expected the new order number (JCP + 6 digits + 001)")
    judge.check("answer_discount", contains_amount(answer, 29.09),
                "expected the SAVE30 discount $29.09")
    judge.check("answer_total", contains_amount(answer, 73.49),
                "expected the order total $73.49")
    # --- DB after-state: one new order + three new order_items, alice's two bag
    # rows removed (any guest-session row the run created is born and deleted
    # inside the window, so it never appears in the snapshot diff).
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
        judge.check("order_row_user_status",
                    row.get("user_id") == 1 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "SAVE30",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 96.98) < 0.005
                    and abs(row.get("discount", 0) - 29.09) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 5.6) < 0.005
                    and abs(row.get("total", 0) - 73.49) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
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
    judge.check("order_items_delta_three_added",
                len(d_items["added"]) == 3 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        units = sorted((r.get("product_id"), r.get("quantity"), r.get("unit_price")) for r in rows)
        boot_units = [u for u in units if u[0] in (105, 110)]
        judge.check("order_items_rows",
                   units == sorted([(61, 1, 31.49), (53, 1, 37.50), boot_units[0]])
                   if len(boot_units) == 1 else False,
                   f"added order_items (product_id, qty, unit_price)={units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 2 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
