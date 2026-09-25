#!/usr/bin/env python3
"""Verify Porsche--14.

Which US state has the most Porsche Centers, how many does it have, and how
many centers does the second-largest state have? Name the Porsche Center in
the largest state whose name comes first alphabetically, and report its phone
number, partner number, city, and its Sunday opening hours exactly as
published.

Frozen ground truth (seed DB): California has the most centers (33); the
second-largest state is Florida (18). The alphabetically first California
center is McKenna Porsche (+1 562-868-3233, partner no. 4500334,
Norwalk, 10830 Firestone Boulevard); its Sunday opening hours: 10:00 - 18:00.
The r2 deepening adds the third-largest state ranking: Texas is third with
13 centers (uniquely ranked).
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_count, contains_phrase, contains_ref, final_answer,
                        navigated_dealer_search, run_verifier)

TASK_ID = "Porsche--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_dealersearch",
                navigated_dealer_search(traj) and navigated_dealer_search(traj, state="CA"),
                "required: /usa/dealersearch/ and /usa/dealersearch/?state=CA")
    # answer gates
    judge.check("answer_largest_state", contains_phrase(answer, "California") or contains_phrase(answer, "CA"),
                "California has the most Porsche Centers")
    judge.check("answer_largest_count", contains_count(answer, 33),
                "33 centers in California")
    judge.check("answer_second_state", contains_phrase(answer, "Florida") or contains_phrase(answer, "FL"),
                "second-largest state: Florida")
    judge.check("answer_second_count", contains_count(answer, 18),
                "18 centers in Florida")
    judge.check("answer_alpha_first_center", contains_phrase(answer, "McKenna Porsche"),
                "alphabetically first California center: McKenna Porsche")
    judge.check("answer_phone", contains_phrase(answer, "562-868-3233"),
                "phone +1 562-868-3233")
    judge.check("answer_partner_no", contains_ref(answer, "4500334"),
                "partner no. 4500334")
    judge.check("answer_city", contains_phrase(answer, "Norwalk"),
                "city Norwalk")
    judge.check("answer_street", contains_phrase(answer, "10830 Firestone Boulevard"),
                "street address 10830 Firestone Boulevard")
    judge.check("answer_sunday_hours",
                (contains_phrase(answer, "10:00") and contains_phrase(answer, "18:00")),
                "Sunday opening hours 10:00 - 18:00")
    # r2 deepening: third-largest state ranking
    judge.check("answer_third_state",
                contains_phrase(answer, "Texas") or contains_phrase(answer, "TX"),
                "third-most Porsche Centers: Texas")
    judge.check("answer_third_count", contains_count(answer, 13),
                "Texas has 13 centers (uniquely ranked third)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
