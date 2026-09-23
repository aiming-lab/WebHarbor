#!/usr/bin/env python3
"""Verify JCPenney--26."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage", "/")
    check_visited_path(judge, traj, "visited_womens_shoes", "/g/shoes/all-womens-shoes")
    # Frozen ground truth (seed DB): Women's Shoes lists 7 products; the cheapest are
    # the St. John's Bay Hope Stacked Heel Booties / Kinnel Flat Heel Booties at $27.99
    # (a price tie — either name is correct), which is below the homepage tile claim
    # "From $31.50", so the claim does not match.
    judge.check("answer_cheapest_price", contains_amount(answer, 27.99),
                "expected the actual cheapest women's shoe $27.99")
    judge.check("answer_cheapest_name", contains_any(answer, ["Hope Stacked Heel Booties", "Kinnel Flat Heel Booties"]),
                "expected the SJB Hope or Kinnel booties (price tie at $27.99)")
    judge.check("answer_claim_verdict", contains_any(answer, ["does not match", "doesn't match",
                                                             "don't match", "do not match",
                                                             "not match", "mismatch", "no match"]),
                "expected the answer to state the homepage claim does not match")
    judge.check("answer_mentions_claim", contains_amount(answer, 31.50),
                "expected the answer to reference the From $31.50 claim")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
