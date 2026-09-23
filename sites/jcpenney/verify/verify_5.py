#!/usr/bin/env python3
"""Verify JCPenney--5."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--5"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    BIOLAGE = "/p/biolage-color-last-shampoo-33-8-oz/pp5004960667"
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_wishlist", "/account/dashboard/wishlist")
    check_visited_path(judge, traj, "visited_biolage_pdp", BIOLAGE)
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): carol's wish list holds 6 items incl. the
    # Biolage Color Last Shampoo ($45.00); removing the St. John's Bay crew neck
    # short sleeve t-shirt leaves 5. carol's seeded bag holds the Maya Brooke
    # Embellished Jacket Dress ($78.39); + shampoo = subtotal $123.39; SAVE30
    # (30%) = $37.02; subtotal >= $75 so shipping is free; tax $7.13; total
    # $93.50, paid with the default American Express ending 1005.
    judge.check("answer_wishlist_remaining", contains_count(answer, 5),
                "expected 5 items remaining on the wish list")
    judge.check("answer_order_number_pattern",
                bool(_re.search(r"JCP\d{6}00?3", answer.replace(" ", ""))),
                "expected the new order number (JCP + 6 digits + 003)")
    judge.check("answer_total", contains_amount(answer, 93.50),
                "expected the order total $93.50")
    # --- DB after-state: one new order + two new order_items, carol's one bag
    # row removed, exactly one wish-list row removed (the SJB crew neck tee).
    check_only_tables_changed(judge, initial_db, after_db,
                              ("orders", "order_items", "cart_items", "wishlist_items"))
    d_orders = table_delta(initial_db, after_db, "orders")
    d_items = table_delta(initial_db, after_db, "order_items")
    d_cart = table_delta(initial_db, after_db, "cart_items")
    d_wish = table_delta(initial_db, after_db, "wishlist_items")
    judge.check("orders_delta_one_added", len(d_orders["added"]) == 1 and not d_orders["removed"]
                and not d_orders["changed"],
                f"orders delta: added={len(d_orders['added'])}")
    if d_orders["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(orders)")]
        row = dict(zip(cols, d_orders["added"][0]))
        judge.check("order_row_user_status",
                    row.get("user_id") == 3 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "SAVE30",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 123.39) < 0.005
                    and abs(row.get("discount", 0) - 37.02) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 7.13) < 0.005
                    and abs(row.get("total", 0) - 93.5) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_shipping_address",
                    row.get("ship_name") == "Carol Davis"
                    and row.get("ship_address") == "515 N State St"
                    and row.get("ship_city") == "Chicago" and row.get("ship_state") == "IL"
                    and row.get("ship_zip") == "60654",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}")
        judge.check("order_row_payment",
                    row.get("payment_type") == "American Express" and row.get("payment_last4") == "1005",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?3", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_two_added",
                len(d_items["added"]) == 2 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        units = sorted((r.get("product_id"), r.get("quantity"), r.get("unit_price")) for r in rows)
        judge.check("order_items_rows",
                    units == sorted([(3, 1, 78.39), (129, 1, 45.00)]),
                    f"added order_items (product_id, qty, unit_price)={units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 1 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")
    judge.check("wishlist_one_removed",
                len(d_wish["removed"]) == 1 and not d_wish["added"] and not d_wish["changed"],
                f"wishlist delta: removed={len(d_wish['removed'])}, added={len(d_wish['added'])}")
    if d_wish["removed"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(wishlist_items)")]
        row = dict(zip(cols, d_wish["removed"][0]))
        judge.check("removed_wishlist_row",
                    row.get("user_id") == 3 and row.get("product_id") == 8,
                    f"removed wishlist row user_id={row.get('user_id')}, "
                    f"product_id={row.get('product_id')} (expected carol / SJB crew neck tee)")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
