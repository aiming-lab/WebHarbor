#!/usr/bin/env python3
"""Verify Instructure--29."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--29"


HELENA_PATH = "/resources/case-studies/digitized-and-disaster-proof-k-12-records-helena-public-schools"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the site search for Parchment then the Helena case study.
    judge.check("visited_search_parchment",
                navigated_search_with(traj, "srch", ["parchment"]),
                "required: /search?srch=Parchment")
    check_visited_path(judge, traj, "visited_helena_case_study", HELENA_PATH)
    # Frozen ground truth (seed DB): the scored search page displays 47 results for
    # "Parchment" (40 resources + 2 careers + 5 events); Helena's stat bar reads
    # Montana / 5,100 students / Adopted Parchment: 2015.
    judge.check("answer_result_count", contains_count(answer, 47),
                "expected 47 search results for Parchment")
    judge.check("answer_state", contains_phrase(answer, "Montana"),
                "expected the state Montana")
    judge.check("answer_adoption_year", contains_count(answer, 2015),
                "expected the adoption year 2015")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
