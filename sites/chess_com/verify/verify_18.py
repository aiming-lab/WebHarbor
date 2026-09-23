#!/usr/bin/env python3
"""Verify the How To Win With Zugzwang lesson course report in Chess.com--18."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the lessons page filtered to one of the course's categories,
    # or the course detail page itself.
    vl = __import__("verify_lib")
    judge.check("visited_zugzwang_category_or_detail",
                vl.navigated_to_path_with_any_param(traj, "/lessons", "category", ["endgames", "tactics"])
                or vl.navigated_to_path(traj, "/lessons/how-to-win-with-zugzwang"),
                "required /lessons?category=endgames|tactics or /lessons/how-to-win-with-zugzwang")
    # Frozen ground truth: 5 lessons; the course carries the Endgames and Tactics category chips
    # (it appears under both filters; naming either one satisfies the question).
    judge.check("answer_lesson_count", contains_count(answer, 5), "expected 5 lessons")
    judge.check("answer_category", contains_any(answer, ["endgames", "endgame", "tactics", "tactic"]),
                "expected 'Endgames' (and/or 'Tactics') as the skill category filter")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
