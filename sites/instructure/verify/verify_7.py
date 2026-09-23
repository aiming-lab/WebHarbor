#!/usr/bin/env python3
"""Verify Instructure--7."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the homepage carries the InstructureCon 2026 banner (the events
    # listing has no InstructureCon row). Homepage-surface task by design.
    check_visited_path(judge, traj, "visited_homepage", "/")
    # Frozen ground truth (index.html InstructureCon banner): "InstructureCon 2026",
    # "Louisville, Kentucky | July 21-23".
    judge.check("answer_event_name", contains_phrase(answer, "InstructureCon 2026"),
                "expected the conference name 'InstructureCon 2026'")
    judge.check("answer_location", contains_phrase(answer, "Louisville, Kentucky"),
                "expected Louisville, Kentucky")
    judge.check("answer_dates",
                (contains_phrase(answer, "July 21-23") or contains_count(answer, 21) and contains_count(answer, 23)),
                "expected the dates July 21-23")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
