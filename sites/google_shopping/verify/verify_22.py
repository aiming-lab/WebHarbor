#!/usr/bin/env python3
"""Verify carol tracking the MVMT Rover Frame in Google Shopping--22."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, run_verifier, table_delta)

TASK_ID = "Google Shopping--22"
MVMT_PATH = "/product/gsac58ccba92d47538"  # MVMT Rover Frame — Blue Light Glasses


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as carol, track from the product page, open tracking.
    check_signed_in_as(judge, traj, "carol.d@test.com", "Carol Davis")
    check_visited_path(judge, traj, "visited_mvmt_product_page", MVMT_PATH)
    check_visited_path(judge, traj, "visited_price_tracking_page", "/tracked")
    # Frozen ground truth: 'MVMT Rover Frame — Blue Light Glasses' at $19.20.
    judge.check("answer_tracked_title", contains_phrase(answer, "MVMT Rover Frame"),
                "expected 'MVMT Rover Frame — Blue Light Glasses'")
    judge.check("answer_tracked_price", contains_price(answer, 19.20), "expected $19.20")
    # DB after-state: exactly one tracked_products row added for (carol, MVMT), nothing else.
    delta = table_delta(initial_db, after_db, "tracked_products")
    judge.check("tracked_exactly_one_row",
                len(delta["added"]) == 1 and delta["added"][0][1] == 3 and delta["added"][0][2] == 36
                and not delta["removed"] and not delta["changed"],
                f"tracked_products delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("tracked_products",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
