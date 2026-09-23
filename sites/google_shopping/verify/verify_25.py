#!/usr/bin/env python3
"""Verify david tracking the most expensive product in Google Shopping--25."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier,
                        table_delta, tracked_pairs)

TASK_ID = "Google Shopping--25"
TRENCH_PATH = "/product/gs3d82a7d8551f4422"  # 'trench' (Reversible, $1,704.00)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as david, use the price-desc search the task names,
    # open the product page, then open the tracking page.
    check_signed_in_as(judge, traj, "david.k@test.com", "David Kim")
    judge.check("visited_desc_sorted_search",
                navigated_search_with(traj, [], exact_params={"sort": "price_desc"}),
                "required=/search?sort=price_desc (empty query, price high to low)")
    check_visited_path(judge, traj, "visited_trench_product_page", TRENCH_PATH)
    check_visited_path(judge, traj, "visited_price_tracking_page", "/tracked")
    # Frozen ground truth: the tracked row is 'trench' at $1,704.00.
    judge.check("answer_tracked_title", contains_phrase(answer, "trench"),
                "expected the exact title 'trench'")
    judge.check("answer_tracked_price", contains_price(answer, 1704.00), "expected $1,704.00")
    # DB after-state: exactly one tracked row added for (david, 'trench' id 59).
    judge.check("david_tracked_set_exact",
                tracked_pairs(after_db, 4) == [(4, 59)],
                f"david tracked_pairs={tracked_pairs(after_db, 4)} expected=[(4, 59)]")
    delta = table_delta(initial_db, after_db, "tracked_products")
    judge.check("tracked_delta_exactly_one",
                len(delta["added"]) == 1 and delta["added"][0][1] == 4 and delta["added"][0][2] == 59
                and not delta["removed"] and not delta["changed"],
                f"tracked_products delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("tracked_products",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
