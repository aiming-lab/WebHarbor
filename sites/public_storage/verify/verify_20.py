#!/usr/bin/env python3
"""Verify Public Storage--20 (read-only) — r2 task text.

I'm comparing a 10'x20' against smaller sizes for my garage contents. On the
10'x20' size-guide FAQ page, how many square feet does it say the unit holds,
what everyday space does it compare the size to, and what does it say the
unit is great for storing? Then tell me the features, in-store monthly price,
online rate, promotion, and monthly saving of the cheapest 10'x20' at the
Bellevue facility on 13640 Bel Red Road, and how many 10'x20' units it lists.

Frozen ground truth (seed DB): the 10'x20' FAQ page says the unit equals
200 square feet, is about the size of a standard one-car garage, and is
great for storing contents of a multi-bedroom home. Facility 81 lists three
10'x20' units; the cheapest is V_1485563 at $414/mo online ($552 in store,
promotion 2ND MONTH FREE, features Ground Floor / Outside Unit, Rollup
Door / Enclosed), saving $138/month online vs in-store.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_facility, navigated_size_faq, navigated_zip_search,
                        run_verifier)

TASK_ID = "Public Storage--20"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_10x20_faq", navigated_size_faq(traj, "10x20-storage-unit"),
                "required: the 10'x20' size-guide FAQ page")
    judge.check("visited_bellevue_search", navigated_zip_search(traj, "bellevue")
                or navigated_zip_search(traj, "13640"),
                "required: Bellevue search results")
    judge.check("visited_facility_81", navigated_facility(traj, 81),
                "required: 13640 Bel Red Road facility page with the 10x20 list")
    # FAQ facts
    judge.check("answer_sqft", contains_count(answer, 200),
                "the 10'x20' holds 200 square feet")
    judge.check("answer_everyday_space", contains_phrase(answer, "one-car garage"),
                "about the size of a standard one-car garage")
    judge.check("answer_great_for", contains_phrase(answer, "multi-bedroom"),
                "great for storing contents of a multi-bedroom home")
    # cheapest 10x20 at the facility
    judge.check("answer_features",
                contains_phrase(answer, "ground floor")
                and (contains_phrase(answer, "outside unit")
                     or contains_phrase(answer, "enclosed")),
                "cheapest 10'x20' features (Ground Floor, Outside Unit, Enclosed)")
    judge.check("answer_instore_price", contains_amount(answer, 552),
                "in-store monthly price $552")
    judge.check("answer_online_rate", contains_amount(answer, 414),
                "online rate $414")
    judge.check("answer_promo", contains_phrase(answer, "2nd month free"),
                "promotion 2ND MONTH FREE")
    judge.check("answer_monthly_saving", contains_amount(answer, 138),
                "monthly saving $138")
    judge.check("answer_unit_count",
                contains_count(answer, 3) or contains_phrase(answer, "three"),
                "the facility lists three 10'x20' units")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
