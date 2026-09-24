#!/usr/bin/env python3
"""Verify Medicare.gov--5 — plan-finder triple comparison for ZIP 62701 (2026).

Read-only task. Ground truth (frozen seed): the Medicare Advantage plans with a
$0 monthly premium for ZIP 62701 are Aetna Medicare Premier (HMO),
UnitedHealthcare Dual Complete (HMO D-SNP), and Wellcare No Premium (HMO); the
higher-rated Medicare drug plan is Humana Walmart Value Rx (PDP) at 4 of 5
stars; Blue Cross Medicare Classic (PPO) has a $54 monthly premium and a
$7,550 in-network out-of-pocket limit.
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_money, contains_phrase, final_answer,
                        query_of_path, run_verifier)

TASK_ID = "Medicare.gov--5"
ZERO_PREMIUM_PLANS = ("Aetna Medicare Premier (HMO)",
                      "UnitedHealthcare Dual Complete (HMO D-SNP)",
                      "Wellcare No Premium (HMO)")
GROUND_TRUTH = ("The $0 monthly premium Medicare Advantage plans for ZIP 62701 are Aetna "
                "Medicare Premier (HMO), UnitedHealthcare Dual Complete (HMO D-SNP), and "
                "Wellcare No Premium (HMO). The higher-rated drug plan is Humana Walmart "
                "Value Rx (PDP) with 4 of 5 stars. Blue Cross Medicare Classic (PPO) has a "
                "$54 monthly premium and a $7,550 in-network out-of-pocket limit.")
QUESTION = ("For ZIP 62701: every Medicare Advantage plan with a $0 monthly premium (full "
            "names), which Medicare drug plan has the higher star rating (and what rating), "
            "and the monthly premium + in-network out-of-pocket limit of Blue Cross "
            "Medicare Classic (PPO)?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    queries = query_of_path(traj, "/plan-compare/search")
    judge.check("searched_ma_plans_62701",
                "zip=62701" in queries and "plan_choice=health" in queries,
                f"observed queries={queries!r}")
    judge.check("searched_drug_plans_62701",
                "zip=62701" in queries and "plan_choice=drug" in queries,
                f"observed queries={queries!r}")
    for plan in ZERO_PREMIUM_PLANS:
        judge.check(f"answer_zero_premium_{plan}",
                    contains_phrase(answer, plan),
                    f"expected the $0-premium plan {plan!r}")
    judge.check("answer_higher_rated_drug_plan",
                contains_phrase(answer, "Humana Walmart Value Rx"),
                "expected Humana Walmart Value Rx (PDP) as the higher-rated drug plan")
    judge.check("answer_drug_plan_4_stars",
                contains_count(answer, 4) and
                (contains_phrase(answer, "star") or contains_phrase(answer, "stars")
                 or contains_phrase(answer, "of 5")),
                "expected the 4-of-5 star rating")
    judge.check("answer_blue_cross_premium_54",
                contains_phrase(answer, "Blue Cross Medicare Classic") and
                contains_money(answer, 54),
                "expected the $54 monthly premium")
    judge.check("answer_oop_limit_7550",
                contains_money(answer, 7550),
                "expected the $7,550 in-network out-of-pocket limit")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
