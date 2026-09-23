#!/usr/bin/env python3
"""Verify Instructure--11."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_leadership", "/about/leadership")
    # Frozen ground truth (seed DB, leaders): the Chief Learning Officer card is
    # Melissa Loble; Steve Daly's bio lists "Before Instructure, Steve held leadership
    # roles at Ivanti, Avocent, and Intel."
    judge.check("answer_clo", contains_phrase(answer, "Melissa Loble"),
                "expected the Chief Learning Officer Melissa Loble")
    judge.check("answer_daly_prior_companies",
                contains_any(answer, ["Ivanti", "Avocent", "Intel"]),
                "expected at least one of Ivanti / Avocent / Intel from Steve Daly's bio")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
