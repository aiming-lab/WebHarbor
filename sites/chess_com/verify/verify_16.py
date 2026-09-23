#!/usr/bin/env python3
"""Verify the Ruy Lopez Top Players report in Chess.com--16."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_ruy_lopez_opening", "/openings/Ruy-Lopez-Opening")
    # Frozen ground truth: top players panel (insertion order) starts
    # Viswanathan Anand, Maxime Vachier-Lagrave, Vasily Smyslov.
    judge.check("answer_top3_in_order",
                phrases_in_order(answer, ["Viswanathan Anand", "Maxime Vachier-Lagrave", "Vasily Smyslov"]),
                "expected Anand, Vachier-Lagrave, Smyslov in order")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
