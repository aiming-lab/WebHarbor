#!/usr/bin/env python3
from verify_lib import (
    Judge, changed_tables, check_common, clicked_transition, contains_all,
    final_answer, load_run, login_submitted_as, parse_args, resolve_db,
    submitted_from_path, visited_in_order, wishlist_snapshot,
)

TASK_ID = "Target--12"
EMAIL = "alice.j@test.com"
SKU = "TGT1012287965"
PRODUCT_PATH = f"/product/{SKU}"
BOTTOM_TOKENS = ("Organic Mini Sandwich", "Cheddar Cheese Crackers")


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_alice", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_save_and_wishlist", visited_in_order(trajectory, [("/login", {}), (PRODUCT_PATH, {}), ("/account/wishlist", {})]), "login, product, wishlist")
    judge.check("product_opened_from_search", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product clicked from search")
    judge.check("wishlist_form_submitted", submitted_from_path(trajectory, PRODUCT_PATH), "detail-page form submitted")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before = wishlist_snapshot(initial, EMAIL); now = wishlist_snapshot(after, EMAIL)
        before_by_id = {row["id"]: row for row in before}; added = [row for row in now if row["id"] not in before_by_id]
        judge.check("exactly_target_added", len(added) == 1 and added[0]["sku"] == SKU and len(now) == len(before) + 1, repr(added))
        judge.check("existing_wishlist_intact", all(row in now for row in before), repr(now))
        judge.check("only_wishlist_changed", changed_tables(initial, after) == {"wishlist_items"}, repr(changed_tables(initial, after)))
        judge.check("answer_bottom_item", contains_all(answer, BOTTOM_TOKENS), repr(answer))
    judge.emit()


if __name__ == "__main__": main()
