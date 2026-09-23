#!/usr/bin/env python3
"""Verify david solves the trainer puzzle and reports the feedback in Chess.com--25."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--25"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: login and the puzzle trainer (unrated or rated route).
    check_signed_in_as(judge, traj, "david.k@test.com", "david_k")
    vl = __import__("verify_lib")
    judge.check("visited_puzzle_trainer",
                any(vl.normalized_url_path(u) in {"/puzzles", "/puzzles/rated"} for u in vl.site_urls(traj)),
                "required /puzzles (or /puzzles/rated)")
    # Frozen ground truth: the trainer's solved feedback is 'Correct! Well played.' and the
    # fresh-database trainer puzzle's goal is 'Win material'.
    judge.check("answer_feedback", contains_phrase(answer, "Correct") and contains_phrase(answer, "Well played"),
                "expected the feedback text 'Correct! Well played.'")
    judge.check("answer_goal", contains_phrase(answer, "Win material"), "expected goal 'Win material'")
    # DB after-state: only david's puzzle attempts may change (rated solves record attempts;
    # unrated practice records none) — everything outside puzzle_attempts is row-identical.
    from verify_lib import check_only_tables_changed, user_id_for_email
    delta = table_delta(initial_db, after_db, "puzzle_attempts")
    david = user_id_for_email(after_db, "david.k@test.com")
    attempts_ok = all(row[1] == david for row in delta["added"]) and not delta["removed"]
    judge.check("puzzle_attempts_only_david", attempts_ok,
                f"delta={delta!r} (added rows must belong to david_k)")
    check_only_tables_changed(judge, initial_db, after_db, {"puzzle_attempts"})



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
