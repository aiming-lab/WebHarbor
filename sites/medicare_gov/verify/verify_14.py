#!/usr/bin/env python3
"""Verify Medicare.gov--14 — new-enrollee orientation chain.

Read-only task. Ground truth (frozen seed): people who start getting Social
Security retirement benefits before 65 get Medicare automatically (others must
actively sign up); the 2026 standard Part B monthly premium is $202.90 paid
each month; the Part A deductible is $1,736 per benefit period; the Medicare
TTY number is 1-877-486-2048; Part A/B sign-up is handled by the Social
Security Administration (SSA); the shingles vaccine costs $0 with Part D.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_money,
                        contains_phrase, contains_phone, final_answer,
                        navigated_to_path, run_verifier)

TASK_ID = "Medicare.gov--14"
GET_STARTED_PAGE = "/basics/get-started-with-medicare"
COSTS_PAGE = "/basics/costs/medicare-costs"
TALK_PAGE = "/talk-to-someone"
COVERAGE_BROWSE = ("/coverage/search", "/coverage/popular-topics", "/coverage/find-alphabetically")
GROUND_TRUTH = ("He gets Medicare automatically because he started getting Social Security "
                "retirement benefits before turning 65. The 2026 standard Part B monthly "
                "premium is $202.90, paid each month. The Part A deductible is $1,736 per "
                "benefit period. The Medicare TTY number is 1-877-486-2048, and Part A/B "
                "sign-up is handled by the Social Security Administration (SSA). The "
                "shingles vaccine costs $0 with Part D (Part D covers all ACIP-recommended "
                "adult vaccines).")
QUESTION = ("A new 65-year-old enrollee already getting Social Security retirement benefits: "
            "does he get Medicare automatically; what are the 2026 standard Part B monthly "
            "premium (and how often paid) and the Part A deductible per benefit period; what "
            "is Medicare's TTY number and which agency handles Part A/B sign-up; and what "
            "would he pay for the shingles vaccine with Part D?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("opened_get_started_page",
                navigated_to_path(traj, GET_STARTED_PAGE),
                f"required_path={GET_STARTED_PAGE}")
    judge.check("opened_costs_page",
                navigated_to_path(traj, COSTS_PAGE),
                f"required_path={COSTS_PAGE}")
    judge.check("opened_talk_page",
                navigated_to_path(traj, TALK_PAGE),
                f"required_path={TALK_PAGE}")
    judge.check("opened_shingles_detail",
                navigated_to_path(traj, "/coverage/shingles-vaccines"),
                "required_path=/coverage/shingles-vaccines")
    judge.check("used_coverage_database",
                any(navigated_to_path(traj, p) for p in COVERAGE_BROWSE),
                f"any_of={COVERAGE_BROWSE}")
    judge.check("answer_automatic_enrollment",
                (contains_phrase(answer, "automatic") or contains_phrase(answer, "automatically"))
                and
                (contains_phrase(answer, "Social Security") or contains_phrase(answer, "SSA")),
                "expected automatic enrollment via Social Security benefits")
    judge.check("answer_part_b_premium_202_90",
                contains_money(answer, 202, 90),
                "expected the $202.90 standard Part B monthly premium")
    judge.check("answer_paid_monthly",
                contains_phrase(answer, "month") or contains_phrase(answer, "monthly"),
                "expected the premium to be paid monthly (each month / monthly)")
    judge.check("answer_part_a_deductible_1736",
                contains_money(answer, 1736),
                "expected the $1,736 Part A deductible per benefit period")
    judge.check("answer_tty_number",
                contains_phone(answer, "8774862048"),
                "expected TTY 1-877-486-2048")
    judge.check("answer_ssa_signups",
                contains_phrase(answer, "Social Security Administration") or
                contains_phrase(answer, "SSA") or
                contains_phrase(answer, "Social Security"),
                "expected the Social Security Administration (SSA)")
    judge.check("answer_shingles_0_with_part_d",
                (contains_money(answer, 0) or contains_phrase(answer, "nothing")
                 or contains_phrase(answer, "no cost") or contains_phrase(answer, "free"))
                and contains_phrase(answer, "part d"),
                "expected $0 / pay nothing with Part D for the shingles vaccine")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
