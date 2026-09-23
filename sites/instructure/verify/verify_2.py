#!/usr/bin/env python3
"""Verify Instructure--2."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--2"


BLOG_PATH = "/resources/blog/minutes-are-wrong-measure"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the site search for "screen time" then the minute-caps blog post.
    judge.check("visited_search_screen_time",
                navigated_search_with(traj, "srch", ["screen", "time"]),
                "required: /search?srch=screen+time")
    check_visited_path(judge, traj, "visited_minutes_blog", BLOG_PATH)
    # Frozen ground truth (seed DB, resources slug minutes-are-wrong-measure):
    # author Dr. Tracy Weeks, publish date Sep 22, 2026.
    judge.check("answer_author", contains_phrase(answer, "Tracy Weeks"),
                "expected the author 'Dr. Tracy Weeks'")
    judge.check("answer_date", contains_date_phrase(answer, "September 22, 2026"),
                "expected the publication date Sep 22, 2026")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
