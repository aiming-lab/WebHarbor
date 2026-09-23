#!/usr/bin/env python3
"""Verify the glasses price-desc top-two report in Google Shopping--7."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier)

TASK_ID = "Google Shopping--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: scored search for 'glasses' sorted by price high to low.
    judge.check("visited_desc_sorted_search",
                navigated_search_with(traj, ["glasses"], exact_params={"sort": "price_desc"}),
                "required=/search?q=glasses&sort=price_desc")
    # Frozen ground truth (seed DB): the two most expensive eyewear rows are both $71.96 —
    # 'BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses' and
    # 'BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses'.
    judge.check("answer_top1_title",
                contains_phrase(answer, "BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses"),
                "expected 'BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses'")
    judge.check("answer_top2_title",
                contains_phrase(answer, "BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses"),
                "expected 'BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses'")
    judge.check("answer_top1_price", contains_price(answer, 71.96), "expected $71.96")
    judge.check("answer_top2_price", contains_price(answer, 71.96), "expected $71.96 (both rows tie)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
