#!/usr/bin/env python3
"""Verify Instructure--28."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--28"


STUDY_PATH = "/resources/research-reports/27890"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Research hub and the 2026 Canvas LMS Educator Impact Study.
    check_visited_path(judge, traj, "visited_research_hub", "/resources/research-reports")
    check_visited_path(judge, traj, "visited_impact_study", STUDY_PATH)
    # Frozen ground truth (seed DB): the study's org type tag is "All" (tags row: Canvas,
    # Evidence, LMS, All); the South Carolina report is "Canvas Use and Efficacy in
    # South Carolina: 2023-24".
    judge.check("answer_org_types", contains_phrase(answer, "All"),
                "expected the org type tag 'All' on the study page")
    judge.check("answer_south_carolina_report",
                contains_all(answer, ["South Carolina", "2023-24"]),
                "expected 'Canvas Use and Efficacy in South Carolina: 2023-24'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
