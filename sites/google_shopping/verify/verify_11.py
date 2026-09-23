#!/usr/bin/env python3
"""Verify the Imily Bela rating report in Google Shopping--11."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_rating, final_answer, run_verifier)

TASK_ID = "Google Shopping--11"
PRODUCT_PATH = "/product/gs712912b8114732bd"  # Imily Bela Elegant Womens Long Oversized Trench Coat


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the rating row is rendered ONLY on the product panel, never on cards.
    check_visited_path(judge, traj, "visited_imily_bela_product_page", PRODUCT_PATH)
    # Frozen ground truth (seed DB, products row 'Imily Bela Elegant Womens Long Oversized
    # Trench Coat Womens Windproof Long Coat'): rating 3.5, review_count 4.
    judge.check("answer_star_rating", contains_rating(answer, 3.5), "expected rating 3.5")
    judge.check("answer_review_count", contains_count(answer, 4), "expected 4 reviews")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
