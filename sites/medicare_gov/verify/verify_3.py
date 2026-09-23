#!/usr/bin/env python3
"""Verify Medicare.gov--3 — Springfield hospital choice + Houston dialysis facility.

Read-only task. Ground truth (frozen seed): among Springfield, IL hospitals,
Memorial Medical Center (3 of 5) has the higher overall rating vs St Johns
Hospital (2 of 5); the Houston, TX dialysis facility with 48 stations and a
late shift is Davita Omni Dialysis Center, phone (713) 665-4747.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_phrase, contains_phone, final_answer,
                        navigated_to_path, query_of_path, run_verifier)

TASK_ID = "Medicare.gov--3"
ST_JOHNS_ID = 3046        # providers.id for St Johns Hospital
MEMORIAL_ID = 3045        # providers.id for Memorial Medical Center (Hospital)
DAVITA_OMNI_ID = 1310     # providers.id for Davita Omni Dialysis Center
GROUND_TRUTH = ("Memorial Medical Center has the higher overall rating of the two "
                "Springfield hospitals: 3 out of 5 (St Johns Hospital is rated 2 out of 5). "
                "The Houston dialysis facility with 48 stations and a late shift is Davita "
                "Omni Dialysis Center, phone (713) 665-4747.")
QUESTION = ("Which Springfield, IL hospital has the higher overall rating (and what is that "
            "rating), and which Houston, TX dialysis facility has 48 stations and offers a "
            "late shift (name and phone number)?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    queries = query_of_path(traj, "/care-compare/search")
    judge.check("searched_hospitals_springfield",
                "type=hospital" in queries and "springfield" in queries,
                f"observed queries={queries!r}")
    judge.check("searched_dialysis_houston",
                "type=dialysisfacility" in queries and "houston" in queries,
                f"observed queries={queries!r}")
    judge.check("opened_both_hospital_details",
                navigated_to_path(traj, f"/care-compare/provider/{ST_JOHNS_ID}") and
                navigated_to_path(traj, f"/care-compare/provider/{MEMORIAL_ID}"),
                f"required providers {ST_JOHNS_ID} and {MEMORIAL_ID}")
    judge.check("opened_davita_omni_detail",
                navigated_to_path(traj, f"/care-compare/provider/{DAVITA_OMNI_ID}"),
                f"required_path=/care-compare/provider/{DAVITA_OMNI_ID}")
    judge.check("answer_memorial_higher_3_of_5",
                contains_phrase(answer, "Memorial") and contains_count(answer, 3) and
                (contains_phrase(answer, "higher") or contains_phrase(answer, "out of 5")
                 or contains_phrase(answer, "of 5") or contains_phrase(answer, "stars")),
                "expected Memorial Medical Center with the higher rating 3 of 5")
    judge.check("answer_davita_omni",
                contains_phrase(answer, "Davita Omni"),
                "expected Davita Omni Dialysis Center")
    judge.check("answer_davita_phone",
                contains_phone(answer, "7136654747"),
                "expected phone (713) 665-4747")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
