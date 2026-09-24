#!/usr/bin/env python3
"""Verify Marriott--15.

Chicago recovery weekend 11/06/2026-11/08/2026: search Chicago hotels and check
the amenity sections of the candidate properties; report every hotel that offers
both a pool and a spa, plus each one's nightly rate and brand.

Frozen ground truth (seed DB): exactly one Chicago hotel offers both Pool and Spa
= JW Marriott Chicago (marsha CHIJW, $304/night, brand JW Marriott).
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_amount,
                        contains_phrase, final_answer, navigated_find_hotels,
                        navigated_hotel_overview, run_verifier)

TASK_ID = "Marriott--15"
HOTEL = "JW Marriott Chicago"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_chicago_search", navigated_find_hotels(traj, "Chicago"),
                "required: /search/findHotels.mi with destinationAddress containing 'Chicago'")
    judge.check("visited_candidate_hotel_page",
                navigated_hotel_overview(traj, "jw-marriott-chicago"),
                "required: the JW Marriott Chicago overview page (amenity section check)")
    judge.check("answer_hotel", contains_phrase(answer, "JW Marriott Chicago"),
                "expected JW Marriott Chicago — the only Chicago hotel with both Pool and Spa")
    judge.check("answer_nightly_rate", contains_amount(answer, 304),
                "expected the $304/night rate")
    judge.check("answer_brand", contains_phrase(answer, "JW Marriott"),
                "expected the brand JW Marriott")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
