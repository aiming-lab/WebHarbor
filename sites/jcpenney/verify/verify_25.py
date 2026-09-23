#!/usr/bin/env python3
"""Verify JCPenney--25."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--25"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_halloween_shop", "/g/shops/halloween-shop")
    # Frozen ground truth (seed DB): the Halloween Shop lists 5 products; cheapest =
    # Layerings Hey Boo 2-pc. Kitchen Towel Set at $8.99; most expensive = Disney
    # Collection Princess Elsa Girls Dress Up Costume at $40.00.
    judge.check("answer_product_count", contains_count(answer, 5),
                "expected 5 products in the Halloween Shop")
    judge.check("answer_cheapest", contains_phrase(answer, "Hey Boo")
                and contains_amount(answer, 8.99),
                "expected the cheapest: Layerings Hey Boo 2-pc. Kitchen Towel Set at $8.99")
    judge.check("answer_most_expensive", contains_phrase(answer, "Elsa")
                and contains_amount(answer, 40.00),
                "expected the most expensive: Disney Princess Elsa costume at $40.00 (rendered $40)")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
