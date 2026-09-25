#!/usr/bin/env python3
"""Verify Public Storage--14 (read-only) — r2 task text.

I work nights and can only reach my unit between 11 PM and 5 AM. What does
the 24-hour self-storage page say 24/7 Access gives you? Does the Kirkland
facility at 724 8th St offer 24/7 access, and what are its access hours on
Sunday? Also report its rating, total review count, and phone number,
whether it offers climate-controlled units, and its cheapest 5'x10' online
rate with that unit's in-store price and promotion.

Frozen ground truth (seed DB): the 24-hour page says 24/7 Access gives you
the freedom to stop by your unit when it works for you. Facility 496
(724 8th St, Kirkland WA) offers 24 Hour Access with Sunday hours 6:00 AM –
10:00 PM, is rated 4.8 with 500 reviews, phone 425-285-7778, offers Climate
Controlled units; its cheapest 5'x10' is V_1454551 at $101/mo online
($169 in store, promotion NO ADMIN FEE & FREE LOCK).
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_facility, navigated_to_path, navigated_zip_search,
                        run_verifier)

TASK_ID = "Public Storage--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_24hr_page",
                navigated_to_path(traj, "/self-storage/24-hour-storage"),
                "required: the 24-hour self-storage page")
    judge.check("visited_kirkland_search", navigated_zip_search(traj, "kirkland")
                or navigated_zip_search(traj, "724 8th"),
                "required: search results for the Kirkland facility")
    judge.check("visited_facility_496", navigated_facility(traj, 496),
                "required: the 724 8th St Kirkland facility page")
    # 24-hour page fact
    judge.check("answer_what_access_gives",
                contains_phrase(answer, "freedom to stop by"),
                "24/7 Access gives you the freedom to stop by your unit")
    # facility facts
    judge.check("answer_24_7_access",
                contains_phrase(answer, "24 hour access")
                or contains_phrase(answer, "24/7"),
                "the facility offers 24/7 access")
    judge.check("answer_sunday_hours", contains_phrase(answer, "6:00 am"),
                "Sunday access hours start 6:00 AM (6:00 AM – 10:00 PM)")
    judge.check("answer_rating", contains_phrase(answer, "4.8"),
                "facility rating 4.8")
    judge.check("answer_review_count", contains_count(answer, 500),
                "total review count 500")
    judge.check("answer_phone", contains_phrase(answer, "425-285-7778"),
                "facility phone 425-285-7778")
    judge.check("answer_climate_controlled",
                contains_phrase(answer, "climate controlled")
                or contains_phrase(answer, "climate-controlled"),
                "the facility offers climate-controlled units")
    # cheapest 5x10
    judge.check("answer_cheapest_5x10", contains_amount(answer, 101),
                "cheapest 5'x10' online rate $101")
    judge.check("answer_instore_price", contains_amount(answer, 169),
                "that unit's in-store price $169")
    judge.check("answer_promo",
                contains_phrase(answer, "no admin fee")
                and contains_phrase(answer, "free lock"),
                "promotion NO ADMIN FEE & FREE LOCK")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
