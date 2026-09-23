#!/usr/bin/env python3
"""Verify Medicare.gov--1 — hip-replacement SNF cost + coverage-rules chain.

Read-only task. Ground truth (frozen seed): 2026 Part A deductible $1,736 per
inpatient hospital benefit period; yearly Part B deductible $283; SNF days
21-100 coinsurance $217 per day; SNF coverage requires a qualifying inpatient
hospital stay of at least 3 days in a row (an ACO approved for the SNF 3-Day
Rule Waiver can replace it); Part A covers at most 100 SNF days per benefit
period; the Part A deductible is not charged again for SNF care in the same
benefit period (days 1-20 $0).

The task wording says "in the same period"; an honest answer echoing that
phrasing must pass, so the not-recharged gate accepts "same period" as well
as "same benefit period" (audit round-2 phrase-acceptance fix — no gate was
weakened: the negation and the same-period scope are still both required).
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_money, contains_phrase, final_answer,
                        navigated_to_path, run_verifier)

TASK_ID = "Medicare.gov--1"
GROUND_TRUTH = ("2026: the Part A deductible is $1,736 for each inpatient hospital benefit "
                "period and the Part B deductible is $283 for the year; inpatient hospital "
                "days 1-60 cost $0 each day after the deductible; skilled nursing facility "
                "days 21-100 cost $217 in coinsurance each day. SNF coverage needs a "
                "qualifying inpatient hospital stay of at least 3 days in a row, unless the "
                "doctor participates in an ACO approved for the SNF 3-Day Rule Waiver; Part "
                "A covers up to 100 SNF days per benefit period, and the Part A deductible "
                "is not charged again for SNF care in the same benefit period (days 1-20 "
                "cost $0).")
QUESTION = ("For a grandfather having hip replacement surgery followed by possible SNF "
            "rehab: what are the 2026 Part A deductible per benefit period, the yearly Part "
            "B deductible, and the daily coinsurance for SNF days 21-100, how many inpatient "
            "hospital days qualify him (can an ACO waiver replace that), how many SNF days "
            "does a benefit period cover, and would he pay the Part A deductible again for "
            "SNF care in the same period?")

COVERAGE_BROWSE = ("/coverage/search", "/coverage/popular-topics", "/coverage/find-alphabetically")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("opened_costs_page",
                navigated_to_path(traj, "/basics/costs/medicare-costs"),
                "required_path=/basics/costs/medicare-costs")
    judge.check("opened_snf_coverage_detail",
                navigated_to_path(traj, "/coverage/skilled-nursing-facility-care"),
                "required_path=/coverage/skilled-nursing-facility-care")
    judge.check("used_coverage_database",
                any(navigated_to_path(traj, p) for p in COVERAGE_BROWSE),
                f"any_of={COVERAGE_BROWSE}")
    judge.check("answer_part_a_deductible_1736",
                contains_money(answer, 1736),
                "expected the $1,736 Part A deductible per benefit period")
    judge.check("answer_part_b_deductible_283",
                contains_money(answer, 283),
                "expected the $283 yearly Part B deductible")
    judge.check("answer_inpatient_days_1_60_zero",
                (contains_money(answer, 0) or contains_phrase(answer, "nothing")
                 or contains_phrase(answer, "no cost")) and
                (contains_phrase(answer, "1-60") or contains_phrase(answer, "1 to 60")
                 or contains_phrase(answer, "first 60")),
                "expected $0 per day for inpatient hospital days 1-60 after the deductible")
    judge.check("answer_snf_217_per_day",
                contains_money(answer, 217) and contains_phrase(answer, "day"),
                "expected $217 coinsurance each day for days 21-100")
    judge.check("answer_3_day_qualifying_stay",
                contains_count(answer, 3) and contains_phrase(answer, "days"),
                "expected a qualifying inpatient stay of at least 3 days")
    judge.check("answer_aco_waiver",
                contains_phrase(answer, "waiver") and
                (contains_phrase(answer, "ACO") or
                 contains_phrase(answer, "Accountable Care Organization")),
                "expected the ACO SNF 3-Day Rule Waiver exception")
    judge.check("answer_100_days_per_benefit_period",
                contains_count(answer, 100) and contains_phrase(answer, "benefit period"),
                "expected the 100-day SNF limit per benefit period")
    judge.check("answer_deductible_not_recharged",
                (contains_phrase(answer, "same benefit period") or
                 contains_phrase(answer, "same period")) and
                (contains_phrase(answer, "not") or contains_phrase(answer, "don't")
                 or contains_phrase(answer, "only once") or contains_phrase(answer, "no")),
                "expected: deductible not charged again in the same benefit period")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
