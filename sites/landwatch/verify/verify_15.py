#!/usr/bin/env python3
"""Verify LandWatch--15 — Farms & Ranches category page first three listings.

Ground truth (frozen seed): 233 listings; the first three are 'Sisterdale
Farms' $19,400,000 (Texas), 'Gaddistown on the Toccoa' $6,500,000 (Georgia),
'Tucked into the Hill Country' $25,950,000 (Texas).
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, phrases_in_order,
                        run_verifier)

TASK_ID = "LandWatch--15"
FARMS_PATH = "/farms-ranches"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_farms_ranches_page", FARMS_PATH)
    judge.check("answer_total_listings", contains_count(answer, 233),
                "expected 233 listings in the results heading")
    judge.check("answer_titles_in_order", phrases_in_order(
        answer, ["Sisterdale Farms", "Gaddistown on the Toccoa",
                 "Tucked into the Hill Country"]),
        "expected the first three titles in page order")
    judge.check("answer_first_price", contains_money(answer, 19400000),
                "expected Sisterdale Farms at $19,400,000")
    judge.check("answer_second_price", contains_money(answer, 6500000),
                "expected Gaddistown on the Toccoa at $6,500,000")
    judge.check("answer_third_price", contains_money(answer, 25950000),
                "expected Tucked into the Hill Country at $25,950,000")
    judge.check("answer_states", contains_phrase(answer, "Georgia") or contains_phrase(answer, "GA"),
                "expected Georgia (or the card's GA state code) among the three states")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
