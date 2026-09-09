#!/usr/bin/env python3
from verify_lib import (
    Judge, cart_snapshot, changed_tables, check_common, clicked_transition,
    contains_all, entered_text, final_answer, load_run, login_submitted_as,
    order_items, orders_snapshot, parse_args, resolve_db, row_dicts,
    submitted_from_path, table_snapshot, visited_in_order,
)

TASK_ID = "Target--17"
EMAIL = "bob.c@test.com"
SKU = "TGT85566854"
PRODUCT_PATH = f"/product/{SKU}"
STORE_SLUG = "denver-stapleton"
SLOT_LABEL = "Tomorrow 9:00 AM - 11:00 AM"


def changed_rows(before: list[tuple], after: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    return ([row for row in before if row not in after], [row for row in after if row not in before])


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_bob", login_submitted_as(trajectory, EMAIL), EMAIL)
    checkpoints = [("/login", {}), (PRODUCT_PATH, {}), ("/cart", {}), ("/checkout/pickup", {}), ("/checkout/payment", {}), ("/checkout/review", {}), ("/checkout/confirmation", {})]
    judge.check("ordered_pickup_checkout", visited_in_order(trajectory, checkpoints), repr(checkpoints))
    judge.check("product_opened_from_search", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product clicked from results")
    judge.check("checkout_forms_submitted", all(submitted_from_path(trajectory, path) for path in (PRODUCT_PATH, "/checkout/pickup", "/checkout/payment", "/checkout/review")), "add, pickup, payment, place order")
    judge.check("requested_quantity_and_pickup_values_entered", entered_text(trajectory, "2", PRODUCT_PATH) and entered_text(trajectory, SLOT_LABEL, "/checkout/pickup"), SLOT_LABEL)
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before_orders = orders_snapshot(initial, EMAIL); after_orders = orders_snapshot(after, EMAIL); before_ids = {row["id"] for row in before_orders}; created = [row for row in after_orders if row["id"] not in before_ids]
        judge.check("bob_cart_clean_before_and_after", cart_snapshot(initial, EMAIL) == [] and cart_snapshot(after, EMAIL) == [], f"before={cart_snapshot(initial, EMAIL)} after={cart_snapshot(after, EMAIL)}")
        judge.check("exactly_one_new_order", len(created) == 1 and len(after_orders) == len(before_orders) + 1, repr(created))
        if len(created) == 1:
            order = created[0]; number = order["order_number"]
            store = row_dicts(after, "SELECT s.slug FROM stores s WHERE s.id=?", (order["store_id"],))
            judge.check("pickup_order_exact", order["fulfillment_method"] == "pickup" and store and store[0]["slug"] == STORE_SLUG and order["pickup_slot_label"] == SLOT_LABEL, repr(order))
            items = order_items(after, number)
            judge.check("only_two_target_items", len(items) == 1 and items[0]["sku"] == SKU and items[0]["quantity"] == 2, repr(items))
            judge.check("answer_real_order_number", contains_all(answer, (number,)), repr(answer))
        removed_inventory, added_inventory = changed_rows(table_snapshot(initial, "store_inventory"), table_snapshot(after, "store_inventory"))
        judge.check("inventory_decrement_exact", len(removed_inventory) == len(added_inventory) == 1 and removed_inventory[0][0] == added_inventory[0][0] and removed_inventory[0][3] - added_inventory[0][3] == 2, f"before={removed_inventory} after={added_inventory}")
        removed_slots, added_slots = changed_rows(table_snapshot(initial, "pickup_slots"), table_snapshot(after, "pickup_slots"))
        judge.check("slot_capacity_decrement_exact", len(removed_slots) == len(added_slots) == 1 and removed_slots[0][0] == added_slots[0][0] and removed_slots[0][5] - added_slots[0][5] == 1, f"before={removed_slots} after={added_slots}")
        expected_tables = {"orders", "order_items", "payment_mocks", "reward_accounts", "reward_activities", "store_inventory", "pickup_slots"}
        judge.check("only_expected_tables_changed", changed_tables(initial, after) == expected_tables, repr(changed_tables(initial, after)))
    judge.emit()


if __name__ == "__main__": main()
