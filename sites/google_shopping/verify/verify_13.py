#!/usr/bin/env python3
"""Verify the BlockBlueLight two-product comparison in Google Shopping--13."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_any,
                        contains_phrase, contains_price, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Google Shopping--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the merchant's scored search (both cards live there).
    judge.check("visited_blockbluelight_search", navigated_search_with(traj, ["blockbluelight"]),
                "required=/search?q=BlockBlueLight")
    # Frozen ground truth (seed DB): exactly two BlockBlueLight rows, both $71.96 —
    # 'BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses' and
    # 'BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses'.
    judge.check("answer_billie_title",
                contains_phrase(answer, "BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses"),
                "expected the Billie title")
    judge.check("answer_taylor_title",
                contains_phrase(answer, "BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses"),
                "expected the Taylor title")
    judge.check("answer_both_prices", contains_price(answer, 71.96), "expected $71.96 (both)")
    judge.check("answer_states_same_price",
                contains_any(answer, ["same price", "cost the same", "same", "equal", "equally",
                                      "identical", "tie", "tied", "both cost"]),
                "expected the answer to state they cost the same")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
