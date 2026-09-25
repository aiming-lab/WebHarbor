#!/usr/bin/env python3
"""Verify Public Storage--6 (read-only) — r2 task text.

Compare the two Bellevue facilities at 13640 Bel Red Road and 12465 Northup
Way. Which one has more customer reviews, and how many more? Then report each
facility's cheapest 5'x5' online rate, the in-store price, promotion, and
phone number at the facility with more reviews, whether it offers 24/7
access, and which facility's cheapest 5'x5' costs less.

Frozen ground truth (seed DB): 12465 Northup Way (facility 68) has 744
reviews vs 13640 Bel Red Road's (facility 81) 698 — 46 more. Facility 68's
cheapest 5'x5' is V_1453658 at $65/mo online ($109 in store, promotion
$1 FIRST MONTH RENT, phone 425-296-6313, 24 Hour Access). Facility 81's
cheapest 5'x5' is $75/mo online, so 12465 Northup Way's costs less.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_facility, navigated_zip_search, run_verifier)

TASK_ID = "Public Storage--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_bellevue_search", navigated_zip_search(traj, "bellevue"),
                "required: Bellevue search results (both facilities)")
    judge.check("visited_facility_68", navigated_facility(traj, 68),
                "required: 12465 Northup Way facility page")
    judge.check("visited_facility_81", navigated_facility(traj, 81),
                "required: 13640 Bel Red Road facility page")
    # which facility has more reviews + how many more
    judge.check("answer_more_reviews_facility",
                contains_phrase(answer, "12465 Northup Way"),
                "12465 Northup Way has more customer reviews")
    judge.check("answer_how_many_more", contains_count(answer, 46),
                "46 more reviews (744 vs 698)")
    judge.check("answer_review_counts",
                contains_count(answer, 744) and contains_count(answer, 698),
                "both review counts reported (744 and 698)")
    # each facility's cheapest 5x5 online rate
    judge.check("answer_68_cheapest_5x5", contains_amount(answer, 65),
                "12465 Northup Way cheapest 5'x5' online rate $65")
    judge.check("answer_81_cheapest_5x5", contains_amount(answer, 75),
                "13640 Bel Red Road cheapest 5'x5' online rate $75")
    # in-store price, promotion, phone at the more-reviewed facility
    judge.check("answer_68_instore", contains_amount(answer, 109),
                "in-store price $109 on that unit")
    judge.check("answer_68_promo", contains_phrase(answer, "first month rent"),
                "promotion $1 FIRST MONTH RENT")
    judge.check("answer_68_phone", contains_phrase(answer, "425-296-6313"),
                "phone number 425-296-6313")
    judge.check("answer_24_7_access",
                contains_phrase(answer, "24 hour access")
                or contains_phrase(answer, "24/7"),
                "facility 68 offers 24/7 access")
    # which facility's cheapest 5x5 costs less
    judge.check("answer_which_costs_less",
                contains_phrase(answer, "12465 northup way")
                and (contains_phrase(answer, "costs less")
                     or contains_phrase(answer, "cheaper")
                     or contains_phrase(answer, "less expensive")),
                "12465 Northup Way's cheapest 5'x5' costs less ($65 vs $75)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
