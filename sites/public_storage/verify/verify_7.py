#!/usr/bin/env python3
"""Verify Public Storage--7 (read-only) — r2 task text.

I'm choosing between the cheapest elevator-access 10'x15' and the cheapest
ground-floor 10'x15' at the Bellevue facility on 13640 Bel Red Road. First
check the 10'x15' size-guide FAQ page: how many square feet does that size
hold, and what everyday space does it compare to? Then report each unit's
online rate, in-store price, and promotion, how much the online price of the
cheaper unit saves versus its own in-store price, and how much more the
ground-floor unit's online rate is.

Frozen ground truth (seed DB): the 10'x15' FAQ says 150 square feet,
comparable to a spare bedroom. Facility 81's cheapest elevator-access 10'x15'
is V_104204 at $199/mo online ($224 in store, $1 FIRST MONTH RENT); the
cheapest ground-floor 10'x15' is V_604211 at $250/mo online ($282 in store,
$1 FIRST MONTH RENT). The elevator unit saves $25/month vs its own in-store
price; the ground-floor online rate is $51 more.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_any_phrase, contains_count,
                        contains_phrase, final_answer, navigated_facility,
                        navigated_size_faq, navigated_zip_search, run_verifier)

TASK_ID = "Public Storage--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_10x15_faq", navigated_size_faq(traj, "10x15-storage-unit"),
                "required: the 10'x15' size-guide FAQ page")
    judge.check("visited_bellevue_search", navigated_zip_search(traj, "bellevue")
                or navigated_zip_search(traj, "13640"),
                "required: Bellevue search results")
    judge.check("visited_facility_81", navigated_facility(traj, 81),
                "required: 13640 Bel Red Road facility page")
    # FAQ facts
    judge.check("answer_sqft", contains_count(answer, 150),
                "a 10'x15' holds 150 square feet")
    judge.check("answer_everyday_space", contains_phrase(answer, "spare bedroom"),
                "the FAQ compares it to a spare bedroom")
    # elevator-access unit
    judge.check("answer_elevator_online", contains_amount(answer, 199),
                "cheapest elevator 10'x15' online rate $199")
    judge.check("answer_elevator_instore", contains_amount(answer, 224),
                "elevator unit in-store price $224")
    judge.check("answer_elevator_promo", contains_phrase(answer, "first month rent"),
                "elevator unit promotion $1 FIRST MONTH RENT")
    # ground-floor unit
    judge.check("answer_ground_online", contains_amount(answer, 250),
                "cheapest ground-floor 10'x15' online rate $250")
    judge.check("answer_ground_instore", contains_amount(answer, 282),
                "ground-floor unit in-store price $282")
    judge.check("answer_ground_promo", contains_phrase(answer, "first month rent"),
                "ground-floor unit promotion $1 FIRST MONTH RENT")
    # derived comparisons
    judge.check("answer_savings_vs_instore", contains_amount(answer, 25),
                "the cheaper (elevator) unit saves $25 vs its own in-store price")
    judge.check("answer_ground_costs_more", contains_amount(answer, 51),
                "the ground-floor online rate is $51 more")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
