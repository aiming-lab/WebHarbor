#!/usr/bin/env python3
"""Verify Medicare.gov--11 — anonymous publications tour + anonymous order.

Read-only task (anonymous orders write no DB row). Ground truth (frozen seed):
'Choosing a Medigap Policy' is product # 02110 in the 'Health care choices'
category; the 'Rights and protections' category lists 4 products (e.g.
'Medicare Rights & Protections' # 11534, 'Medicare Appeals' # 11525, '4R's for
Fighting Medicare Fraud' # 11610, 'Protecting Yourself from Fraud' # 10111);
the anonymous order confirmation reads 'We received your request'.
"""

from verify_lib import (Judge, MEDIGAP_PUB_NUMBER, advisory_llm_answer,
                        check_read_only, check_trajectory_identity,
                        contains_count, contains_phrase, final_answer,
                        navigated_to_path, query_of_path, run_verifier)

TASK_ID = "Medicare.gov--11"
MEDIGAP_ORDER_PAGE = f"/publication-ordering/{MEDIGAP_PUB_NUMBER}"
RIGHTS_CATEGORY_TITLES = (
    "Medicare Rights & Protections", "Medicare Appeals",
    "4R's for Fighting Medicare Fraud", "Protecting Yourself from Fraud",
)
GROUND_TRUTH = ("'Choosing a Medigap Policy' is product # 02110 in the 'Health care "
                "choices' category. The 'Rights and protections' category lists 4 "
                "products, including 'Medicare Rights & Protections' (# 11534). The "
                "anonymous order of 1 Standard Print copy of the Medigap guide shipped to "
                "302 W Edwards St, Springfield, IL 62704 was received (product # 02110, "
                "ships within 2-4 weeks).")
QUESTION = ("Find 'Choosing a Medigap Policy' (product number + category), count the "
            "products in the 'Rights and protections' category (name one of them), then "
            "anonymously order 1 Standard Print copy of the Medigap guide to 302 W Edwards "
            "St, Springfield, IL 62704 and confirm.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    pub_queries = query_of_path(traj, "/publications/search")
    judge.check("searched_publications_medigap",
                "choosing a medigap policy" in pub_queries,
                f"observed queries={pub_queries!r}")
    judge.check("filtered_rights_category",
                "rights and protections" in pub_queries,
                f"observed queries={pub_queries!r}")
    judge.check("opened_medigap_order_page",
                navigated_to_path(traj, MEDIGAP_ORDER_PAGE),
                f"required_path={MEDIGAP_ORDER_PAGE}")
    judge.check("answer_medigap_product_number",
                contains_phrase(answer, MEDIGAP_PUB_NUMBER) or contains_phrase(answer, "2110"),
                f"expected product number {MEDIGAP_PUB_NUMBER!r}")
    judge.check("answer_medigap_category",
                contains_phrase(answer, "health care choices"),
                "expected the 'Health care choices' category")
    judge.check("answer_rights_category_count",
                contains_count(answer, 4) and contains_phrase(answer, "rights and protections"),
                "expected 4 products in the Rights and protections category")
    named = [t for t in RIGHTS_CATEGORY_TITLES if contains_phrase(answer, t)]
    judge.check("answer_one_rights_title",
                bool(named),
                f"expected one of {RIGHTS_CATEGORY_TITLES!r}; matched={named!r}")
    judge.check("answer_order_confirmed",
                contains_phrase(answer, "received") or contains_phrase(answer, "on its way")
                or contains_phrase(answer, "confirmed") or contains_phrase(answer, "went through"),
                "expected an order confirmation")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
