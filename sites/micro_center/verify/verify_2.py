#!/usr/bin/env python3
"""Verify Micro Center--2.

Find the open-box laptop whose Excellent condition saves the most versus
buying new, plus the runner-up. Report each one's name with its new and
Excellent-condition prices, every open-box condition and price offered for
the winner, how many stores have the winner in stock, and whether it is in
stock at the Cambridge, MA store.

Frozen ground truth (seed DB): among the 11 open-box laptops the biggest
Excellent savings is the Dell Precision 7780 Mobile Workstation 17.3"
(671164): new $3,219.99, Excellent $2,720.96 (saves $499.03), also offered
Satisfactory $2,714.66; in stock at 23 of 30 stores; OUT of stock at
Cambridge (121). Runner-up: Microsoft Surface Laptop (Wi-Fi) 7th Edition
ZGQ-00001 (681059): new $1,399.99, Excellent $1,019.01 (saves $380.98).
The Precision 3680 desktop has larger savings but is not a laptop (near-miss).
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_any, contains_count, contains_phrase, final_answer,
                        navigated_to_path, navigated_to_product, run_verifier)

TASK_ID = "Micro Center--2"
WINNER_PID = 671164
RUNNER_PID = 681059
WINNER_NEW = 3219.99
WINNER_EXCELLENT = 2720.96
WINNER_SATISFACTORY = 2714.66
RUNNER_NEW = 1399.99
RUNNER_EXCELLENT = 1019.01
WINNER_STORES = 23
NOT_IN_STOCK_PHRASES = ("not in stock", "out of stock", "isn't in stock",
                        "is not in stock", "not available", "no stock", "not stocked")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_open_box_listing",
                navigated_to_path(traj, "/site/products/open-box.aspx"),
                "required_path=/site/products/open-box.aspx")
    judge.check("visited_winner_page", navigated_to_product(traj, WINNER_PID),
                f"required_product_id={WINNER_PID} (Precision 7780)")
    judge.check("visited_runner_up_page", navigated_to_product(traj, RUNNER_PID),
                f"required_product_id={RUNNER_PID} (Surface Laptop ZGQ-00001)")
    judge.check("answer_names_winner",
                contains_phrase(answer, "precision") and contains_phrase(answer, "7780"),
                "expected_tokens=['precision', '7780']")
    judge.check("answer_quotes_winner_new_price", contains_amount(answer, WINNER_NEW),
                f"expected_new_price={WINNER_NEW}")
    judge.check("answer_quotes_winner_excellent_price",
                contains_amount(answer, WINNER_EXCELLENT),
                f"expected_excellent_price={WINNER_EXCELLENT}")
    judge.check("answer_names_runner_up", contains_phrase(answer, "surface"),
                "expected_token='surface' (runner-up is the Surface Laptop ZGQ-00001)")
    judge.check("answer_quotes_runner_new_price", contains_amount(answer, RUNNER_NEW),
                f"expected_new_price={RUNNER_NEW}")
    judge.check("answer_quotes_runner_excellent_price",
                contains_amount(answer, RUNNER_EXCELLENT),
                f"expected_excellent_price={RUNNER_EXCELLENT}")
    judge.check("answer_quotes_winner_satisfactory_price",
                contains_amount(answer, WINNER_SATISFACTORY),
                f"expected_satisfactory_price={WINNER_SATISFACTORY}")
    judge.check("answer_quotes_winner_store_count",
                contains_count(answer, WINNER_STORES),
                f"expected_stores={WINNER_STORES}")
    judge.check("answer_states_cambridge_availability",
                contains_phrase(answer, "cambridge")
                and contains_any(answer, NOT_IN_STOCK_PHRASES),
                "expected: Cambridge + an out-of-stock phrase (the winner is not "
                "in stock at Cambridge, MA)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
