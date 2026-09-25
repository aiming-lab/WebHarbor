#!/usr/bin/env python3
"""Verify JCPenney--4."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--4"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    MAXBLACKOUT = "/p/max-blackout-mystique-grommet-top-100-blackout-single-curtain-panel/ppr5007989193"
    check_visited_path(judge, traj, "visited_register", "/register")
    judge.check("visited_blackout_search_sorted",
                navigated_search_sorted(traj, "blackout curtain panel", "price_high"),
                "required: /s/blackout curtain panel with sortBy=price_high")
    check_visited_path(judge, traj, "visited_panel_pdp", MAXBLACKOUT)
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): the most expensive Blackout-named panel is the
    # Max Blackout Mystique Grommet Top 100% Blackout Single Curtain Panel at
    # $52.50 (the high-to-low sort lists the Gwen Leaf panel first, so the answer
    # must pick the most expensive panel whose NAME includes Blackout). A freshly
    # registered account has an empty bag -> subtotal $52.50; AUTUMN (25%) =
    # $13.12; subtotal < $75 so shipping is $8.95; tax on the discounted subtotal
    # $3.25; total $51.58, paid with the new Visa ending 1111, shipped to the new
    # address (412 Cedar St, Denver, CO 80203).
    judge.check("answer_panel_bought",
                contains_all(answer, ["Max Blackout Mystique"]),
                "expected the Max Blackout Mystique panel as the one bought")
    judge.check("answer_order_number_pattern",
                bool(_re.search(r"JCP\d{6}00?5", answer.replace(" ", ""))),
                "expected the new order number (JCP + 6 digits + 005)")
    judge.check("answer_discount", contains_amount(answer, 13.12),
                "expected the AUTUMN discount $13.12")
    judge.check("answer_total", contains_amount(answer, 51.58),
                "expected the order total $51.58")
    # --- DB after-state: one new user (Pat Quinn, password Shopper123!), one new
    # order + one new order item; the in-run cart row is born and deleted inside
    # the window, so cart_items stays row-identical.
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "orders", "order_items"))
    d_users = table_delta(initial_db, after_db, "users")
    d_orders = table_delta(initial_db, after_db, "orders")
    d_items = table_delta(initial_db, after_db, "order_items")
    judge.check("users_delta_one_added",
                len(d_users["added"]) == 1 and not d_users["removed"] and not d_users["changed"],
                f"users delta: added={len(d_users['added'])}, removed={len(d_users['removed'])}, "
                f"changed={len(d_users['changed'])}")
    new_user_id = None
    if d_users["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(users)")]
        urow = dict(zip(cols, d_users["added"][0]))
        new_user_id = urow.get("id")
        new_email = str(urow.get("email", "")).lower()
        judge.check("new_user_email_fresh",
                    new_email not in {"alice.j@test.com", "bob.c@test.com",
                                      "carol.d@test.com", "david.k@test.com"} and "@" in new_email,
                    f"new user email={new_email!r}")
        judge.check("new_user_name_pinned",
                    urow.get("first_name") == "Pat" and urow.get("last_name") == "Quinn",
                    f"name={urow.get('first_name')} {urow.get('last_name')}")
        judge.check("new_user_password_pinned",
                    urow.get("password_hash") == stable_password_hash("Shopper123!"),
                    "the task pins the password Shopper123! — the row hash must match")
    judge.check("orders_delta_one_added", len(d_orders["added"]) == 1 and not d_orders["removed"]
                and not d_orders["changed"],
                f"orders delta: added={len(d_orders['added'])}")
    if d_orders["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(orders)")]
        row = dict(zip(cols, d_orders["added"][0]))
        judge.check("order_row_user_status",
                    row.get("user_id") == new_user_id and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "AUTUMN",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 52.5) < 0.005
                    and abs(row.get("discount", 0) - 13.12) < 0.005
                    and abs(row.get("shipping", 0) - 8.95) < 0.005
                    and abs(row.get("tax", 0) - 3.25) < 0.005
                    and abs(row.get("total", 0) - 51.58) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_user_is_new",
                    new_user_id is not None and row.get("user_id") == new_user_id,
                    f"user_id={row.get('user_id')}, expected the freshly registered user")
        judge.check("order_row_new_address",
                    row.get("ship_name") == "Pat Quinn"
                    and row.get("ship_address") == "412 Cedar St"
                    and row.get("ship_city") == "Denver" and row.get("ship_state") == "CO"
                    and row.get("ship_zip") == "80203",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}, "
                    f"ship_city={row.get('ship_city')!r}")
        judge.check("order_row_new_card",
                    row.get("payment_type") == "Visa" and row.get("payment_last4") == "1111",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?5", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_one_added",
                len(d_items["added"]) == 1 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        irow = dict(zip(cols, d_items["added"][0]))
        judge.check("order_item_row",
                    irow.get("product_id") == 92 and irow.get("quantity") == 1
                    and abs(irow.get("unit_price", 0) - 52.50) < 0.005,
                    f"item (product_id, qty, unit_price)="
                    f"({irow.get('product_id')}, {irow.get('quantity')}, {irow.get('unit_price')})")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
