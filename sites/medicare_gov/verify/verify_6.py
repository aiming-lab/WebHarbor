#!/usr/bin/env python3
"""Verify Medicare.gov--6 — Denver 5-star MA plan + anonymous handbook order.

Read-only task (an anonymous publication order writes no DB row; the app only
persists orders for logged-in accounts). Ground truth (frozen seed): the
5-star Medicare Advantage plan for ZIP 80204 is Kaiser Permanente Medicare Plus
(HMO) at a $62 monthly premium; the 'Medicare & You 2027' handbook is product
# 10050 and the anonymous order confirmation reads 'We received your request'.
"""

from verify_lib import (HANDBOOK_PUB_NUMBER, Judge, advisory_llm_answer,
                        check_read_only, check_trajectory_identity,
                        contains_count, contains_money, contains_phrase,
                        final_answer, navigated_to_path, query_of_path,
                        run_verifier)

TASK_ID = "Medicare.gov--6"
ORDER_PAGE = f"/publication-ordering/{HANDBOOK_PUB_NUMBER}"
GROUND_TRUTH = ("The Medicare Advantage plan rated 5 stars for ZIP 80204 (Denver) is "
                "Kaiser Permanente Medicare Plus (HMO) with a $62 monthly premium. The "
                "anonymous order of 2 Standard Print copies of 'Medicare & You 2027' "
                "(product # 10050) to 12 Elm Court, Denver, CO 80204 was received: the "
                "confirmation page says the request was received and ships within 2-4 "
                "weeks.")
QUESTION = ("Which Medicare Advantage plan for ZIP 80204 is rated 5 stars (name and monthly "
            "premium), and confirm the anonymous order of 2 Standard Print copies of the "
            "'Medicare & You 2027' handbook shipped to 12 Elm Court, Denver, CO 80204.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    plans = query_of_path(traj, "/plan-compare/search")
    judge.check("searched_ma_plans_80204",
                "zip=80204" in plans and "plan_choice=health" in plans,
                f"observed queries={plans!r}")
    judge.check("searched_publications_for_handbook",
                "medicare" in query_of_path(traj, "/publications/search") and
                "you" in query_of_path(traj, "/publications/search"),
                "expected a publications search for the Medicare & You handbook")
    judge.check("opened_handbook_order_page",
                navigated_to_path(traj, ORDER_PAGE),
                f"required_path={ORDER_PAGE}")
    judge.check("answer_5star_plan_name",
                contains_phrase(answer, "Kaiser Permanente Medicare Plus"),
                "expected Kaiser Permanente Medicare Plus (HMO)")
    judge.check("answer_5star_plan_premium",
                contains_money(answer, 62),
                "expected the $62 monthly premium")
    judge.check("answer_handbook_product_number",
                contains_phrase(answer, HANDBOOK_PUB_NUMBER) or
                contains_count(answer, 10050),
                "expected product # 10050")
    judge.check("answer_order_confirmed",
                contains_phrase(answer, "received") or contains_phrase(answer, "on its way")
                or contains_phrase(answer, "confirmed") or contains_phrase(answer, "went through"),
                "expected an order confirmation")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
