#!/usr/bin/env python3
"""Verify JCPenney--12."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--12"


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_count, contains_phrase, final_answer, run_verifier,
                        table_delta)

TASK_ID = "JCPenney--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_wishlist", "/account/dashboard/wishlist")
    # Frozen ground truth (seed DB): alice's wish list has 4 items; removing the
    # St. John's Bay mock neck t-shirt (product_id 11) leaves 3 —
    # St. John's Bay Plus Split Tie Neck 3/4 Sleeve Blouse $24.49,
    # St. John's Bay Mens Long Sleeve Classic Fit Flannel Shirt $20.99,
    # London Times ... Balloon Chiffon Animal Fit + Flare Dress $51.79.
    judge.check("answer_remaining_count", contains_count(answer, 3),
                "expected 3 remaining wish-list items")
    judge.check("answer_remaining_one", contains_all(answer, ["Split Tie Neck", "24.49"]),
                "expected the SJB plus split tie blouse at $24.49")
    judge.check("answer_remaining_two", contains_all(answer, ["Classic Fit Flannel Shirt", "20.99"]),
                "expected the SJB mens flannel shirt at $20.99")
    judge.check("answer_remaining_three", contains_all(answer, ["London Times", "51.79"]),
                "expected the London Times dress at $51.79")
    judge.check("removed_item_gone", "Mock Neck" not in answer,
                "the removed mock neck t-shirt must not be listed as remaining")
    # --- DB after-state: exactly one wish-list row removed (alice, product_id 11).
    check_only_tables_changed(judge, initial_db, after_db, ("wishlist_items",))
    delta = table_delta(initial_db, after_db, "wishlist_items")
    judge.check("wishlist_delta_exact",
                len(delta["removed"]) == 1 and not delta["added"] and not delta["changed"],
                f"wishlist delta: removed={len(delta['removed'])}, added={len(delta['added'])}, "
                f"changed={len(delta['changed'])}")
    if delta["removed"]:
        cols = [r["name"] for r in __import__("verify_lib").db_query(initial_db, "PRAGMA table_info(wishlist_items)")]
        row = dict(zip(cols, delta["removed"][0]))
        judge.check("removed_row_is_mock_neck",
                    row.get("user_id") == 1 and row.get("product_id") == 11,
                    f"removed row user_id={row.get('user_id')}, product_id={row.get('product_id')}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
