#!/usr/bin/env python3
"""Verify Medicare.gov--2 — Boston referral (family practice) + BIDMC hospital check.

Read-only task. Ground truth (frozen seed): the doctors & clinicians search near
Boston, MA with keyword "family practice" returns 12 results, the first
(closest) being Bailey Walker Goodwin (Family practice); Beth Israel Deaconess
Medical Center has emergency services (Yes), ownership type Voluntary
non-profit - Private, and reports 15 patient experience measures.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_to_path,
                        query_of_path, run_verifier)

TASK_ID = "Medicare.gov--2"
BIDMC_PROVIDER_ID = 258           # providers.id for Beth Israel Deaconess Medical Center
GROUND_TRUTH = ("The doctors & clinicians search near Boston, MA with keyword 'family "
                "practice' lists 12 results; the first (closest) is Bailey Walker Goodwin, "
                "a Family practice doctor, for the referral. Beth Israel Deaconess Medical "
                "Center has emergency services (Yes), its ownership type is Voluntary "
                "non-profit - Private, and it reports 15 patient experience measures.")
QUESTION = ("In the provider directory, search doctors & clinicians near Boston, MA with "
            "the keyword 'family practice' (how many results, name and specialty of the "
            "first/closest one), then check Beth Israel Deaconess Medical Center among "
            "hospitals near Boston, MA: emergency services, ownership type, and how many "
            "patient experience measures it reports.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    queries = query_of_path(traj, "/care-compare/search")
    judge.check("searched_physicians_boston_family_practice",
                "type=physician" in queries and "family practice" in queries
                and "boston" in queries,
                f"observed queries={queries!r}")
    judge.check("searched_hospitals_boston_beth_israel",
                "type=hospital" in queries and "beth israel" in queries,
                f"observed queries={queries!r}")
    judge.check("opened_bidmc_detail",
                navigated_to_path(traj, f"/care-compare/provider/{BIDMC_PROVIDER_ID}"),
                f"required_path=/care-compare/provider/{BIDMC_PROVIDER_ID}")
    judge.check("answer_12_doctor_results",
                contains_count(answer, 12),
                "expected 12 results for the family-practice search")
    judge.check("answer_closest_doctor",
                contains_phrase(answer, "Bailey Walker Goodwin"),
                "expected Bailey Walker Goodwin as the first (closest) result")
    judge.check("answer_specialty_family_practice",
                contains_phrase(answer, "family practice"),
                "expected the Family practice specialty")
    judge.check("answer_bidmc_emergency_yes",
                contains_phrase(answer, "emergency") and
                (contains_phrase(answer, "yes") or contains_phrase(answer, "has")),
                "expected emergency services: Yes")
    judge.check("answer_bidmc_ownership",
                contains_phrase(answer, "voluntary non-profit") and
                contains_phrase(answer, "private"),
                "expected ownership type Voluntary non-profit - Private")
    judge.check("answer_bidmc_15_experience_measures",
                contains_count(answer, 15) and contains_phrase(answer, "patient experience"),
                "expected 15 patient experience measures")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
