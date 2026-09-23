#!/usr/bin/env python3
"""Verify Instructure--27."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--27"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Blogs hub with the Topic filter Artificial Intelligence.
    judge.check("visited_blog_hub_with_ai_filter",
                navigated_listing_with_filter(traj, "blog", "topic", "Artificial Intelligence"),
                "required: /resources/blog?topic=Artificial+Intelligence")
    # Frozen ground truth (seed DB): 25 blog posts tagged Artificial Intelligence; the
    # AI literacy post is "Finding the Sensible Middle: AI Literacy, Cognitive
    # Offloading, and Student Voice in the Classroom".
    judge.check("answer_blog_count", contains_count(answer, 25),
                "expected 25 matching blog posts")
    judge.check("answer_target_blog",
                contains_all(answer, ["Finding the Sensible Middle", "Cognitive Offloading",
                                      "Student Voice in the Classroom"]),
                "expected the AI literacy blog title")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
