#!/usr/bin/env python3
"""Verify Instructure--3."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the On-Demand Webinars hub with the Org Type filter "Business".
    judge.check("visited_webinars_hub_with_business_filter",
                navigated_listing_with_filter(traj, "webinars", "org", "Business"),
                "required: /resources/webinars?org=Business")
    # Frozen ground truth (seed DB): 13 webinars tagged org Business; the first (list
    # order 1) is "Staying Competitive in a Skills-Based World: The New Rules for Growth
    # and Employability in the Age..." (the listing card renders the upstream-truncated
    # title with an ellipsis).
    judge.check("answer_result_count", contains_count(answer, 13),
                "expected 13 results with the Org Type filter Business")
    judge.check("answer_first_webinar",
                contains_all(answer, ["Staying Competitive in a Skills-Based World",
                                     "New Rules for Growth and Employability"]),
                "expected the first webinar 'Staying Competitive in a Skills-Based World: "
                "The New Rules for Growth and Employability in the Age...'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
