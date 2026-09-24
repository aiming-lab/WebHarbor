#!/usr/bin/env python3
"""Verify Medicare.gov--13 — hospice eligibility rules + Houston hospice agency.

Read-only task. Ground truth (frozen seed): hospice care requires Part A; the
hospice doctor and the regular doctor certify terminal illness (life
expectancy of 6 months or less); hospice care from a Medicare-approved hospice
costs $0 (up to a $5 copay per prescription for outpatient drugs). The first
hospice listed for Houston, TX is 1st Choice Hospice LLC, phone
(936) 295-7100.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_money, contains_phrase, contains_phone,
                        final_answer, navigated_to_path, query_of_path,
                        run_verifier)

TASK_ID = "Medicare.gov--13"
FIRST_HOSPICE_ID = 1459          # providers.id for 1st Choice Hospice LLC
COVERAGE_BROWSE = ("/coverage/search", "/coverage/popular-topics", "/coverage/find-alphabetically")
GROUND_TRUTH = ("Hospice care requires Medicare Part A; the hospice doctor and the regular "
                "doctor (if any) certify that the patient is terminally ill, with a life "
                "expectancy of 6 months or less. Hospice care from a Medicare-approved hospice "
                "costs $0 (up to a $5 copay per outpatient drug prescription). The first hospice "
                "listed near Houston, TX is 1st Choice Hospice LLC, phone (936) 295-7100.")
QUESTION = ("Which part of Medicare is required for hospice care and who must certify the "
            "terminal illness; then find hospice agencies near Houston, TX — open the first "
            "one listed and report its name and phone number.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("opened_hospice_coverage_detail",
                navigated_to_path(traj, "/coverage/hospice-care"),
                "required_path=/coverage/hospice-care")
    judge.check("used_coverage_database",
                any(navigated_to_path(traj, p) for p in COVERAGE_BROWSE),
                f"any_of={COVERAGE_BROWSE}")
    care = query_of_path(traj, "/care-compare/search")
    judge.check("searched_hospice_houston",
                "type=hospice" in care and "houston" in care,
                f"observed queries={care!r}")
    judge.check("opened_first_hospice_detail",
                navigated_to_path(traj, f"/care-compare/provider/{FIRST_HOSPICE_ID}"),
                f"required_path=/care-compare/provider/{FIRST_HOSPICE_ID}")
    judge.check("answer_part_a",
                contains_phrase(answer, "part a"),
                "expected Part A for hospice coverage")
    judge.check("answer_certification",
                contains_phrase(answer, "hospice doctor") and
                (contains_phrase(answer, "regular doctor") or contains_phrase(answer, "your doctor")),
                "expected hospice doctor + regular doctor certification")
    judge.check("answer_hospice_cost",
                (contains_money(answer, 0) or contains_phrase(answer, "nothing")
                 or contains_phrase(answer, "no cost")) and
                (contains_phrase(answer, "$5") or contains_phrase(answer, "copay")
                 or contains_phrase(answer, "copayment")),
                "expected $0 for hospice care from a Medicare-approved hospice (up to $5 per "
                "outpatient drug prescription)")
    judge.check("answer_6_months",
                contains_count(answer, 6) and contains_phrase(answer, "months"),
                "expected a life expectancy of 6 months or less")
    judge.check("answer_first_hospice_name",
                contains_phrase(answer, "1st Choice Hospice"),
                "expected 1st Choice Hospice LLC")
    judge.check("answer_first_hospice_phone",
                contains_phone(answer, "9362957100"),
                "expected phone (936) 295-7100")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
