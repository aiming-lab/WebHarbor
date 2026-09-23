#!/usr/bin/env python3
"""Verify the Sicilian Defense opening report in Chess.com--14."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sicilian_opening", "/openings/Sicilian-Defense")
    # Frozen ground truth: ECO B20, 919742 games in the explorer, main line 1.e4 c5.
    judge.check("answer_eco_code", contains_phrase(answer, "B20"), "expected 'B20'")
    judge.check("answer_games_played", contains_amount(answer, 919742), "expected 919,742 games")
    judge.check("answer_main_line_moves", contains_phrase(answer, "e4") and contains_phrase(answer, "c5"),
                "expected the first two moves 1.e4 c5")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
