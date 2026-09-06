#!/usr/bin/env python3
from verify_lib import (
    Judge, cart_snapshot, changed_tables, check_common, clicked_transition,
    final_answer, has_money, load_run, login_submitted_as, parse_args,
    resolve_db, row_dicts, submitted_from_path, visited_in_order,
)

TASK_ID = "Target--10"
EMAIL = "carol.d@test.com"
SKU = "TGT91151386"
PRODUCT_PATH = f"/product/{SKU}"


def cart_subtotal(path: str, email: str) -> float:
    rows = row_dicts(path, "SELECT c.quantity,p.price,COALESCE(pp.price,0) AS plan_price FROM cart_items c JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id LEFT JOIN protection_plans pp ON pp.id=c.protection_plan_id WHERE lower(u.email)=lower(?)", (email,))
    return round(sum((row["price"] + row["plan_price"]) * row["quantity"] for row in rows), 2)


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_carol", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_product_add_cart", visited_in_order(trajectory, [("/login", {}), (PRODUCT_PATH, {}), ("/cart", {})]), "login, product, cart")
    judge.check("product_opened_from_search", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product clicked from search")
    judge.check("add_form_submitted", submitted_from_path(trajectory, PRODUCT_PATH), "product form submitted")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before = cart_snapshot(initial, EMAIL); now = cart_snapshot(after, EMAIL)
        before_by_sku = {row["sku"]: row for row in before}; now_by_sku = {row["sku"]: row for row in now}
        judge.check("target_absent_initially", SKU not in before_by_sku, repr(before))
        judge.check("target_added_once", SKU in now_by_sku and now_by_sku[SKU]["quantity"] == 1, repr(now))
        unchanged_existing = all(sku in now_by_sku and {k: v for k, v in row.items() if k != "id"} == {k: v for k, v in now_by_sku[sku].items() if k != "id"} for sku, row in before_by_sku.items())
        judge.check("existing_cart_rows_unchanged", unchanged_existing and set(now_by_sku) == set(before_by_sku) | {SKU}, repr(now))
        judge.check("only_cart_table_changed", changed_tables(initial, after) == {"cart_items"}, repr(changed_tables(initial, after)))
        subtotal = cart_subtotal(after, EMAIL)
        judge.check("answer_subtotal", has_money(answer, subtotal), f"expected={subtotal:.2f} answer={answer!r}")
    judge.emit()


if __name__ == "__main__": main()
