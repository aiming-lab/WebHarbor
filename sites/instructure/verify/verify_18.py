#!/usr/bin/env python3
"""Verify Instructure--18."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--18"

from verify_lib import changed_tables, saved_of, user_by_email, resource_by_slug, table_delta

MADISON_SLUG = "staying-course-better-benchmarks-madison-county"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed DB): alice has 4 saved resources; the only case study
    # among them is "Staying the Course for Better Benchmarks in Madison County".
    judge.check("answer_saved_count", contains_count(answer, 4),
                "expected 4 saved resources before the removal")
    judge.check("answer_case_study_title",
                contains_all(answer, ["Staying the Course", "Madison County"]),
                "expected the Madison County case study title in the saved list")
    judge.check("answer_removal_confirmation",
                contains_all(answer, ["Removed", "from your saved resources"]),
                "expected the removal confirmation message")
    # DB delta: exactly alice's saved row for the Madison County case study is removed,
    # nothing else changes.
    alice = user_by_email(initial_db, "alice.j@test.com")
    res = resource_by_slug(initial_db, MADISON_SLUG)
    delta = table_delta(initial_db, after_db, "saved_resources")
    removed_pairs = [(row[1], row[2]) for row in delta["removed"]]
    judge.check("db_saved_madison_removed",
                delta["added"] == [] and delta["changed"] == []
                and removed_pairs == [(alice["id"], res["id"])],
                f"saved_resources delta={delta!r}, expected removed "
                f"[(user {alice['id']}, resource {res['id']})]")
    check_only_tables_changed(judge, initial_db, after_db, ["saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
