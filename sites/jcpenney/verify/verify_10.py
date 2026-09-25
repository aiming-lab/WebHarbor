#!/usr/bin/env python3
"""Verify JCPenney--10."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--10"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    PAPELL = "/p/papell-boutique-womens-v-neck-short-sleeve-cap-evening-gown/ppr5008618161"
    check_signed_in_as(judge, traj, "david.k@test.com")
    check_visited_path(judge, traj, "visited_giftcards", "/gift-cards")
    judge.check("entered_gift_card_number",
                any("6249881234570021" in t for t in
                    (__import__("verify_lib").input_texts(traj))),
                "expected the gift card number 6249881234570021 entered on the balance checker")
    check_visited_path(judge, traj, "visited_wishlist", "/account/dashboard/wishlist")
    check_visited_path(judge, traj, "visited_gown_pdp", PAPELL)
    check_visited_path(judge, traj, "visited_checkout_shipping", "/checkout/shipping")
    check_visited_path(judge, traj, "visited_checkout_payment", "/checkout/payment")
    check_visited_path(judge, traj, "visited_checkout_review", "/checkout/review")
    judge.check("visited_confirmation",
                any(normalized_url_path(u).startswith("/checkout/confirmation/")
                    for u in site_urls(traj)),
                "required: /checkout/confirmation/<order-number>")
    # Frozen ground truth (seed DB): gift card 6249881234570021 carries a $21.00
    # balance (both checks show $21.00 — a balance check never debits). david's
    # seeded bag holds the Threadmade Harvest Sentiment napkins ($25.19 x2) and
    # the St. John's Bay Plus Cable Knit pullover ($26.59 x1); + the Papell
    # Boutique evening gown ($89.59) = subtotal $166.56; no coupon; subtotal
    # >= 75 so shipping is free; tax $13.74; total $180.30, paid with the
    # default Visa ending 0679, with the pinned gift message stored on the order.
    GIFT_MESSAGE = "Congratulations on your graduation! Love, Aunt June"
    judge.check("answer_balance", contains_amount(answer, 21.00),
                "expected the gift card balance $21.00")
    judge.check("answer_order_number_pattern",
                bool(_re.search(r"JCP\d{6}00?4", answer.replace(" ", ""))),
                "expected the new order number (JCP + 6 digits + 004)")
    judge.check("answer_total", contains_amount(answer, 180.30),
                "expected the order total $180.30")
    # --- DB after-state: one new order + three items, david's two bag rows
    # removed, the order row carrying exactly the pinned gift message.
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
                    row.get("user_id") == 4 and row.get("status") == "Processing",
                    f"user_id={row.get('user_id')}, status={row.get('status')!r}")
        judge.check("order_row_coupon", row.get("coupon_code") == "",
                    f"coupon_code={row.get('coupon_code')!r}")
        judge.check("order_row_amounts",
                    abs(row.get("subtotal", 0) - 166.56) < 0.005
                    and abs(row.get("discount", 0) - 0.0) < 0.005
                    and abs(row.get("shipping", 0) - 0.0) < 0.005
                    and abs(row.get("tax", 0) - 13.74) < 0.005
                    and abs(row.get("total", 0) - 180.3) < 0.005,
                    f"subtotal={row.get('subtotal')}, discount={row.get('discount')}, "
                    f"shipping={row.get('shipping')}, tax={row.get('tax')}, "
                    f"total={row.get('total')}")
        judge.check("order_row_shipping_address",
                    row.get("ship_name") == "David Kim"
                    and row.get("ship_address") == "77 E Nationwide Blvd"
                    and row.get("ship_city") == "Columbus" and row.get("ship_state") == "OH"
                    and row.get("ship_zip") == "43215",
                    f"ship_name={row.get('ship_name')!r}, ship_address={row.get('ship_address')!r}")
        judge.check("order_row_payment",
                    row.get("payment_type") == "Visa" and row.get("payment_last4") == "0679",
                    f"payment={row.get('payment_type')} {row.get('payment_last4')}")
        judge.check("order_row_gift_message",
                    str(row.get("gift_message") or "") == GIFT_MESSAGE,
                    f"gift_message={row.get('gift_message')!r}")
        judge.check("order_number_format", bool(_re.fullmatch(r"JCP\d{6}00?4", row.get("order_number", ""))),
                    f"order_number={row.get('order_number')!r}")
    judge.check("order_items_delta_three_added",
                len(d_items["added"]) == 3 and not d_items["removed"] and not d_items["changed"],
                f"order_items delta: added={len(d_items['added'])}")
    if d_items["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(order_items)")]
        rows = [dict(zip(cols, r)) for r in d_items["added"]]
        units = sorted((r.get("product_id"), r.get("quantity"), r.get("unit_price")) for r in rows)
        judge.check("order_items_rows",
                    units == sorted([(86, 2, 25.19), (25, 1, 26.59), (1, 1, 89.59)]),
                    f"added order_items (product_id, qty, unit_price)={units}")
    judge.check("cart_items_cleared", len(d_cart["removed"]) == 2 and not d_cart["added"]
                and not d_cart["changed"],
                f"cart delta: removed={len(d_cart['removed'])}, added={len(d_cart['added'])}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
