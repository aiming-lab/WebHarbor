#!/usr/bin/env python3
"""Verify the cheapest >=50%-discounted trench coat under $70 in Google Shopping--16."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Google Shopping--16"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: a trench-coat scored search (any filter strategy is legitimate).
    judge.check("visited_trench_search", navigated_search_with(traj, ["trench", "coat"]),
                "required=/search?q=<trench coat>")
    # Frozen ground truth (seed DB): qualifying rows (discount >= 50% and price < $70) are
    # 'Women's Loft Drapey Trench Coat' $51.95 (74%), "Women's Loft Versa Seasonless Stretch
    # Trench Coat in Stripe" $64.00 (64%), "Gap Factory Women's Modern Trench Coat" $64.99 (50%),
    # "Women's Abercrombie & Fitch A&F Carrie Long Trench Coat" $69.99 (56%); cheapest is the
    # LOFT Drapey coat at $51.95.
    judge.check("answer_cheapest_title", contains_phrase(answer, "Women's Loft Drapey Trench Coat"),
                "expected 'Women's Loft Drapey Trench Coat'")
    judge.check("answer_merchant", contains_phrase(answer, "LOFT"), "expected merchant LOFT")
    judge.check("answer_current_price", contains_price(answer, 51.95), "expected $51.95")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
