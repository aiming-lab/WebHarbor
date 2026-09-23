#!/usr/bin/env python3
"""Verify Instructure--26."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the homepage statistics section. Homepage-surface task by design.
    check_visited_path(judge, traj, "visited_homepage", "/")
    # Frozen ground truth (seed DB stat_cards): "2B assessment scores created via Mastery"
    # and "7K K-12 schools love Parchment".
    judge.check("answer_mastery_scores",
                contains_any(answer, ["2B", "2 billion", "two billion"]),
                "expected 2B assessment scores created via Mastery")
    judge.check("answer_parchment_schools",
                contains_any(answer, ["7K", "7,000", "seven thousand"]),
                "expected 7K K-12 schools loving Parchment")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
