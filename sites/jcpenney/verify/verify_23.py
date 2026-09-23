#!/usr/bin/env python3
"""Verify JCPenney--23."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--23"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_plus_size_gallery", "/g/women/womens-plus-size")
    # Frozen ground truth (seed DB): Plus Size lists 3 products —
    # St. John's Bay Plus Cuffed Long Sleeve ... Button-Down Shirt $20.99,
    # St. John's Bay Plus Split Tie Neck 3/4 Sleeve Blouse $24.49,
    # Ashley Graham Women's Plus Goddess Gather Mesh Dress $37.80 (the most
    # expensive; card shows $37.80 - $90.00).
    judge.check("answer_product_count", contains_count(answer, 3),
                "expected 3 products in Plus Size")
    judge.check("answer_brands", contains_all(answer, ["St. John's Bay", "Ashley Graham"]),
                "expected the brands ST. JOHN'S BAY and Ashley Graham")
    judge.check("answer_most_expensive", contains_phrase(answer, "Ashley Graham")
                and contains_amount(answer, 37.80),
                "expected the Ashley Graham dress as most expensive at $37.80 (rendered $37.8)")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
