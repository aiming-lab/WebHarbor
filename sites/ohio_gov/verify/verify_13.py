#!/usr/bin/env python3
"""Verify Ohio.gov--13.

Topic-hub chain: the Top Services hub in the Residents section (how many
resources it lists + the first three), the Unclaimed Funds resource (which
department helps Ohioans claim funds held in their names + two examples of
what unclaimed funds include), and the Money & Finance hub under Home &
Community (how many resources it lists + the title of the first one).

Frozen ground truth (tracked data snapshot): the Residents > Top Services hub
lists 13 resources, the first three being Birth and Death Certificates,
Business Search, and Cash Assistance (Ohio Works First). The Unclaimed Funds
page names the Department of Commerce and lists examples including old bank
accounts, forgotten rent or utility deposits, uncashed checks, and unused
insurance policies. The Money & Finance hub lists 8 resources, the first
being Annual Sales Tax Holiday.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, contains_any, final_answer,
                        navigated_to_path_any, run_verifier)

TASK_ID = "Ohio.gov--13"
HUB_PATHS = ("/residents/topic-hubs/top-services", "/residents/top-services")
UNCLAIMED = "/residents/resources/unclaimed-funds"
MONEY_FINANCE_PATHS = ("/residents/home-and-community/money-and-finance/money-and-finance",
                       "/residents/topic-hubs/home-and-community/money-and-finance/money-and-finance",
                       "/residents/topic-hubs/money-and-finance")
EXAMPLES = ["old bank accounts", "forgotten rent or utility deposits",
            "uncashed checks", "unused insurance policies"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the Top Services hub, the Unclaimed Funds resource,
    # and the Money & Finance hub
    judge.check("visited_top_services_hub", navigated_to_path_any(traj, HUB_PATHS),
                f"required: one of {HUB_PATHS}")
    check_visited_path(judge, traj, "visited_unclaimed_funds", UNCLAIMED)
    judge.check("visited_money_finance_hub", navigated_to_path_any(traj, MONEY_FINANCE_PATHS),
                f"required: one of {MONEY_FINANCE_PATHS}")
    # answer: hub count, first three, department, two examples, money hub facts
    judge.check("answer_hub_count", contains_count(answer, 13),
                "expected: 13 resources listed in Top Services")
    judge.check("answer_first_three",
                contains_phrase(answer, "birth and death certificates")
                and contains_phrase(answer, "business search")
                and contains_phrase(answer, "cash assistance"),
                "expected first three: Birth and Death Certificates; Business Search; "
                "Cash Assistance (Ohio Works First)")
    judge.check("answer_department", contains_phrase(answer, "department of commerce"),
                "expected: the Department of Commerce helps Ohioans claim funds held in their names")
    judge.check("answer_two_examples",
                sum(1 for e in EXAMPLES if contains_phrase(answer, e)) >= 2,
                f"expected at least 2 of {EXAMPLES!r}")
    judge.check("answer_money_hub_count", contains_count(answer, 8),
                "expected: 8 resources listed in the Money & Finance hub")
    judge.check("answer_money_hub_first",
                contains_phrase(answer, "annual sales tax holiday"),
                "expected first Money & Finance resource: Annual Sales Tax Holiday")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
