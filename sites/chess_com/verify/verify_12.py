#!/usr/bin/env python3
"""Verify the Misc news category report in Chess.com--12."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_misc_category", "/news/category/misc")
    # Frozen ground truth: exactly 1 article in the misc category; most recent title
    # 'Welcome to the Worst Band Class Ever' (emoji optional in the answer).
    judge.check("answer_article_count", contains_count(answer, 1), "expected 1 article")
    judge.check("answer_most_recent_title", contains_phrase(answer, "Welcome to the Worst Band Class Ever"),
                "expected 'Welcome to the Worst Band Class Ever'")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
