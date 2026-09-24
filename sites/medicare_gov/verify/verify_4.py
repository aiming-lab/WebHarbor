#!/usr/bin/env python3
"""Verify Medicare.gov--4 — Denver 5-star nursing home count + ZIP 80204 walker supplier.

Read-only task. Ground truth (frozen seed): the nursing homes search near
Denver, CO lists 60 facilities of which 12 have an overall rating of 5 stars
(two of them: Advanced Health Care of Aurora, Ahc of Lakewood, LLC); the
medical equipment & suppliers search for ZIP 80204 with keyword 'walkers'
returns 21 suppliers, the closest being King Soopers Pharmacy #001, phone
(303) 571-1943.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_phrase, contains_phone, final_answer,
                        query_of_path, run_verifier)

TASK_ID = "Medicare.gov--4"
# The 12 five-star Denver nursing homes (distinctive name prefixes, frozen seed).
FIVE_STAR_NAMES = (
    "Advanced Health Care of Aurora", "Ahc of Lakewood", "Arvada Care",
    "Berkley Manor", "Briarwood", "Edgewater Health", "Hallmark Nursing",
    "Highland Park", "Littleton Care", "Parkview Care", "Sloan's Lake",
    "Suites at Clermont Park",
)
GROUND_TRUTH = ("12 of the 60 nursing homes near Denver, CO have an overall rating of 5 "
                "stars, including Advanced Health Care of Aurora and Ahc of Lakewood, LLC. "
                "The closest walker supplier for ZIP 80204 is King Soopers Pharmacy #001, "
                "phone (303) 571-1943.")
QUESTION = ("How many nursing homes near Denver, CO are rated 5 stars overall (name two of "
            "them), and which is the closest supplier of walkers for ZIP code 80204 "
            "(name and phone number)?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    care = query_of_path(traj, "/care-compare/search")
    dme = query_of_path(traj, "/medical-equipment-suppliers/results")
    judge.check("searched_nursing_homes_denver",
                "type=nursinghome" in care and "denver" in care,
                f"observed care-compare queries={care!r}")
    judge.check("searched_dme_80204_walkers",
                "location=80204" in dme and "walkers" in dme,
                f"observed dme queries={dme!r}")
    judge.check("answer_12_five_star_nursing_homes",
                contains_count(answer, 12) and
                (contains_phrase(answer, "nursing home") or contains_phrase(answer, "nursing homes")
                 or contains_phrase(answer, "5 star") or contains_phrase(answer, "5 stars")
                 or contains_phrase(answer, "five star") or contains_phrase(answer, "five stars")),
                "expected 12 five-star nursing homes")
    named = [name for name in FIVE_STAR_NAMES if contains_phrase(answer, name)]
    judge.check("answer_two_5_star_names",
                len(named) >= 2,
                f"expected two of {FIVE_STAR_NAMES!r}; matched={named!r}")
    judge.check("answer_closest_walker_supplier",
                contains_phrase(answer, "King Soopers Pharmacy #001"),
                "expected King Soopers Pharmacy #001 as the closest supplier")
    judge.check("answer_supplier_phone",
                contains_phone(answer, "3035711943"),
                "expected phone (303) 571-1943")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
