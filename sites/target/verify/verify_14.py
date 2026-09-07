#!/usr/bin/env python3
from verify_lib import (
    Judge, changed_tables, check_common, clicked_transition, contains_all,
    final_answer, load_run, login_submitted_as, parse_args, resolve_db,
    submitted_from_path, visited_in_order, wishlist_snapshot,
)

TASK_ID = "Target--14"
EMAIL = "alice.j@test.com"
REMOVED_SKU = "TGT12954143"
REMAINING_TOKEN_GROUPS = (
    ("Katie's Burrata Margherita",),
    ("Cinnamon Toast Crunch",),
    ("Organic Mini Sandwich", "Cheddar Cheese Crackers"),
)


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_alice", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_login_to_wishlist", visited_in_order(trajectory, [("/login", {}), ("/account", {}), ("/account/wishlist", {})]), "login, account, wishlist")
    judge.check("clicked_wishlist", clicked_transition(trajectory, "/account", "/account/wishlist"), "wishlist opened from account")
    judge.check("removal_form_submitted", submitted_from_path(trajectory, "/account/wishlist", "/account/wishlist"), "wishlist removal submitted")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before = wishlist_snapshot(initial, EMAIL); now = wishlist_snapshot(after, EMAIL)
        removed = [row for row in before if row not in now]
        judge.check("only_named_item_removed", len(removed) == 1 and removed[0]["sku"] == REMOVED_SKU and len(now) == len(before) - 1, repr(removed))
        judge.check("remaining_rows_exact", all(row in before for row in now), repr(now))
        judge.check("only_wishlist_changed", changed_tables(initial, after) == {"wishlist_items"}, repr(changed_tables(initial, after)))
        judge.check("answer_names_all_remaining", all(contains_all(answer, group) for group in REMAINING_TOKEN_GROUPS), repr(answer))
    judge.emit()


if __name__ == "__main__": main()
