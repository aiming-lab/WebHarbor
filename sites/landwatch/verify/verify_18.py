#!/usr/bin/env python3
"""Verify LandWatch--18 — Homepage featured-listing carousel, first three properties.

Ground truth (frozen seed): 'Potomac Ridge View Estate' $450,000 / 20.18
Acres / West Virginia; 'Rustic Cabin on 25 Acres' $299,000 / 25 Acres /
Virginia; 'Skyline Creekside Log Cabin' $799,900 / 5.87 Acres / Utah.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_money,
                        contains_phrase, contains_phrase_without_prefix,
                        final_answer, phrases_in_order, run_verifier)

TASK_ID = "LandWatch--18"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage", "/")
    judge.check("answer_states_in_order", phrases_in_order(
        answer, ["West Virginia", "Utah"]) or phrases_in_order(
        answer, ["WV", "UT"]),
        "expected West Virginia (or WV) before Utah (or UT), carousel order")
    judge.check("answer_second_state_is_plain_virginia",
                contains_phrase_without_prefix(answer, "Virginia", "West ")
                or contains_phrase(answer, "VA"),
                "the second property is in Virginia (or VA), not West Virginia")
    judge.check("answer_first_price", contains_money(answer, 450000),
                "expected $450,000 for the first featured property")
    judge.check("answer_first_acres", contains_acres(answer, 20.18),
                "expected 20.18 Acres for the first featured property")
    judge.check("answer_second_price", contains_money(answer, 299000),
                "expected $299,000 for the second featured property")
    judge.check("answer_second_acres", contains_acres(answer, 25),
                "expected 25 Acres for the second featured property")
    judge.check("answer_third_price", contains_money(answer, 799900),
                "expected $799,900 for the third featured property")
    judge.check("answer_third_acres", contains_acres(answer, 5.87),
                "expected 5.87 Acres for the third featured property")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
