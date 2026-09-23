#!/usr/bin/env python3
"""Verify alice's preseeded shopping list report in Google Shopping--20."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, contains_price, final_answer,
                        run_verifier)

TASK_ID = "Google Shopping--20"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth gate: sign in as the demo account, then open the shopping list.
    check_signed_in_as(judge, traj, "alice.j@test.com", "Alice Johnson")
    check_visited_path(judge, traj, "visited_shopping_list", "/saved")
    # Frozen ground truth (seed DB, saved_items): alice's list holds exactly one row —
    # "Gap Factory Women's Modern Trench Coat" (Gap Factory, $64.99).
    judge.check("answer_saved_title", contains_phrase(answer, "Gap Factory Women's Modern Trench Coat"),
                "expected 'Gap Factory Women's Modern Trench Coat'")
    judge.check("answer_saved_merchant", contains_phrase(answer, "Gap Factory"),
                "expected merchant Gap Factory")
    judge.check("answer_saved_price", contains_price(answer, 64.99), "expected $64.99")
    # Reading the list must not write anything.
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
