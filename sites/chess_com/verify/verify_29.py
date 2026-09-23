#!/usr/bin/env python3
"""Verify david marks Gambit Buffet complete and reports the progress in Chess.com--29."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--29"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: login and the course page.
    check_signed_in_as(judge, traj, "david.k@test.com", "david_k")
    check_visited_path(judge, traj, "visited_gambit_buffet_course", "/lessons/gambit-buffet")
    # Frozen ground truth: the course page shows 'Your progress: 16/16 lessons completed.'
    import re
    from verify_lib import normalize_text
    normalized = normalize_text(answer)
    judge.check("answer_progress_text",
                __import__("verify_lib")._affirmative_search(r"(?<![\d.,])16\s*(?:/|of)\s*16(?!=\d)", normalized),
                "expected '16/16 lessons completed'")
    # DB after-state: exactly one lesson_progress row added (david -> gambit-buffet course 4,
    # lessons_done 16); david has no seed progress row.
    from verify_lib import check_only_tables_changed
    delta = table_delta(initial_db, after_db, "lesson_progress")
    added_ok = len(delta["added"]) == 1 and delta["added"][0][1] == 1179 and delta["added"][0][2] == 4         and delta["added"][0][3] == 16
    judge.check("lesson_progress_exact_delta",
                added_ok and not delta["removed"] and not delta["changed"],
                f"delta={delta!r} (expected exactly +1 row user_id=1179, course_id=4, lessons_done=16)")
    check_only_tables_changed(judge, initial_db, after_db, {"lesson_progress"})



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
