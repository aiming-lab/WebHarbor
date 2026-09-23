#!/usr/bin/env python3
"""Verify the 2025-03-15 archive puzzle report in Chess.com--20.

Re-anchored (review R2): the archive listing rows carry title / curator /
comment count, which leaked the original answers at the listing layer, so the
question now asks for detail-page-unique facts — the puzzle number, the theme
from the details panel, and the first move of the revealed solution line.
"""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--20"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the archive listing AND the 2025-03-15 puzzle detail page.
    vl = __import__("verify_lib")
    judge.check("visited_puzzle_archive",
                vl.navigated_to_path(traj, "/puzzles/archive") or vl.navigated_to_path(traj, "/daily/archive"),
                "required /puzzles/archive or /daily/archive")
    check_visited_path(judge, traj, "visited_target_puzzle", "/puzzles/problem/73")
    # Frozen ground truth (detail-page-only facts): the puzzle page shows
    # 'Puzzle #12976', the details panel theme is 'Tactics', and the solution
    # line revealed by the button starts with 1. Qc4+ (Qc4+ Kg7 Qxa2 gxh4 h3).
    judge.check("answer_puzzle_number", contains_amount(answer, 12976),
                "expected puzzle #12976")
    judge.check("answer_theme", contains_phrase(answer, "Tactics"),
                "expected the 'Tactics' theme")
    judge.check("answer_first_solution_move",
                contains_any(answer, ["Qc4+", "Qc4"]),
                "expected the solution to start with Qc4+")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
