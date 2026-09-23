#!/usr/bin/env python3
"""Verify the 'Yes Sir' search report in Google Shopping--10."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_percent,
                        contains_phrase, contains_price, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Google Shopping--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the scored search for 'Yes Sir'.
    judge.check("visited_yes_sir_search", navigated_search_with(traj, ["yes", "sir"]),
                "required=/search?q=Yes Sir")
    # Frozen ground truth (seed DB, products row 'Fashion Nova Yes Sir Bluelight'):
    # $5.99, 33% OFF, merchant Fashion Nova.
    judge.check("answer_full_title", contains_phrase(answer, "Fashion Nova Yes Sir Bluelight"),
                "expected 'Fashion Nova Yes Sir Bluelight'")
    judge.check("answer_current_price", contains_price(answer, 5.99), "expected $5.99")
    judge.check("answer_discount_pct", contains_percent(answer, 33), "expected 33% OFF")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
