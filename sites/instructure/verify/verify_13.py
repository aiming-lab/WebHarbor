#!/usr/bin/env python3
"""Verify Instructure--13."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_newsroom", "/news")
    # Frozen ground truth (seed DB, news_items): "What Every Educator Needs to Know
    # About AI in 2025" | The Ed Up Experience Podcast | January 16, 2025 | Ryan Lufkin.
    judge.check("answer_publication_date", contains_date_phrase(answer, "January 16, 2025"),
                "expected the publication date January 16, 2025")
    judge.check("answer_spokesperson", contains_phrase(answer, "Ryan Lufkin"),
                "expected the spokesperson Ryan Lufkin")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
