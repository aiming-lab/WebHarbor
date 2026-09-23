#!/usr/bin/env python3
"""Verify the Klassy 'Compare with similar items' composition report in Google Shopping--12.

Re-anchored in the contributor's reviewer-round fix (47326b6d): the rail's merchant mix
and order are rendered only on the product panel.
"""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Google Shopping--12"
PRODUCT_PATH = "/product/gsb43c9633d0a7d9f3"  # Klassy - Blue Light Blocking Glasses Tortie Brown


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Compare-with-similar section is rendered only on the product page.
    check_visited_path(judge, traj, "visited_klassy_product_page", PRODUCT_PATH)
    # Frozen ground truth (seed DB): the Klassy rail lists the first 8 eyewear rows by
    # position (excluding Klassy): 2 of them are sold by BlockBlueLight (NightFall Billie
    # and Nightfall Taylor), and the first listed product is
    # "AE Classic Tortoise Shell Blue Light Glasses Women's" (American Eagle Outfitters).
    judge.check("answer_rail_blockbluelight_count", contains_count(answer, 2),
                "expected 2 BlockBlueLight products in the rail")
    judge.check("answer_rail_first_title",
                contains_phrase(answer, "AE Classic Tortoise Shell Blue Light Glasses Women's"),
                "expected 'AE Classic Tortoise Shell Blue Light Glasses Women's' as the first listed")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
