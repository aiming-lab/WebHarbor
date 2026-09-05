#!/usr/bin/env python3
from verify_lib import (
    Judge, cart_snapshot, changed_tables, check_common, clicked_transition,
    contains_all, entered_text, final_answer, load_run, login_submitted_as,
    order_items, orders_snapshot, parse_args, resolve_db, row_dicts,
    submitted_from_path, table_snapshot, visited_in_order,
)

TASK_ID = "Target--11"
EMAIL = "bob.c@test.com"
SKU = "TGT94640332"
PRODUCT_PATH = f"/product/{SKU}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_bob", login_submitted_as(trajectory, EMAIL), EMAIL)
    checkpoints = [("/login", {}), ("/search", {"q": "Tide Ultra Oxi"}), (PRODUCT_PATH, {}), ("/cart", {}), ("/checkout/shipping", {}), ("/checkout/payment", {}), ("/checkout/review", {}), ("/checkout/confirmation", {})]
    judge.check("ordered_delivery_checkout", visited_in_order(trajectory, checkpoints), repr(checkpoints))
    judge.check("clicked_tide_result", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product clicked from search")
    judge.check("checkout_forms_submitted", all(submitted_from_path(trajectory, path) for path in (PRODUCT_PATH, "/checkout/shipping", "/checkout/payment", "/checkout/review")), "add, shipping, payment, place order")
    address_inputs = all(entered_text(trajectory, value, "/checkout/shipping") for value in ("123 Main St", "Denver", "CO", "80202"))
    judge.check("requested_address_entered", address_inputs, "exact address fields")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before_orders = orders_snapshot(initial, EMAIL); after_orders = orders_snapshot(after, EMAIL)
        before_ids = {row["id"] for row in before_orders}; created = [row for row in after_orders if row["id"] not in before_ids]
        judge.check("bob_cart_clean_before_and_after", cart_snapshot(initial, EMAIL) == [] and cart_snapshot(after, EMAIL) == [], f"before={cart_snapshot(initial, EMAIL)} after={cart_snapshot(after, EMAIL)}")
        judge.check("exactly_one_new_order", len(created) == 1 and len(after_orders) == len(before_orders) + 1 and all(row in after_orders for row in before_orders), repr(created))
        if len(created) == 1:
            order = created[0]; number = order["order_number"]
            exact_order = order["fulfillment_method"] == "delivery" and order["shipping_street"] == "123 Main St" and order["shipping_city"] == "Denver" and order["shipping_state"] == "CO" and order["shipping_zip"] == "80202"
            judge.check("delivery_address_exact", exact_order, repr(order))
            items = order_items(after, number)
            judge.check("only_target_item_ordered", len(items) == 1 and items[0]["sku"] == SKU and items[0]["quantity"] == 1, repr(items))
            payments = row_dicts(after, "SELECT * FROM payment_mocks WHERE order_id=?", (order["id"],))
            judge.check("one_payment_for_order", len(payments) == 1 and abs(payments[0]["amount"] - order["total"]) < 0.005, repr(payments))
            judge.check("answer_real_order_number", contains_all(answer, (number,)), repr(answer))
            before_reward = row_dicts(initial, "SELECT ra.* FROM reward_accounts ra JOIN users u ON u.id=ra.user_id WHERE lower(u.email)=lower(?)", (EMAIL,))[0]
            after_reward = row_dicts(after, "SELECT ra.* FROM reward_accounts ra JOIN users u ON u.id=ra.user_id WHERE lower(u.email)=lower(?)", (EMAIL,))[0]
            judge.check("reward_points_exact", after_reward["points_balance"] == before_reward["points_balance"] + int(order["subtotal"]), f"before={before_reward} after={after_reward}")
            before_activities = table_snapshot(initial, "reward_activities"); after_activities = table_snapshot(after, "reward_activities")
            new_activities = [row for row in after_activities if row not in before_activities]
            judge.check("one_reward_activity", len(new_activities) == 1 and new_activities[0][2] == int(order["subtotal"]) and all(row in after_activities for row in before_activities), repr(new_activities))
            for table in ("order_items", "payment_mocks"):
                before_rows = table_snapshot(initial, table); after_rows = table_snapshot(after, table)
                judge.check(f"existing_{table}_intact", all(row in after_rows for row in before_rows), f"before={len(before_rows)} after={len(after_rows)}")
        expected_tables = {"orders", "order_items", "payment_mocks", "reward_accounts", "reward_activities"}
        judge.check("only_expected_tables_changed", changed_tables(initial, after) == expected_tables, repr(changed_tables(initial, after)))
    judge.emit()


if __name__ == "__main__": main()
