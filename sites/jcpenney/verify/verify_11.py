#!/usr/bin/env python3
"""Verify JCPenney--11."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_amount, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_wishlist", "/account/dashboard/wishlist")
    # Frozen ground truth (seed DB, carol's wish list): 6 items —
    # St. John's Bay Crew Neck Short Sleeve T-Shirt $11.20,
    # St. John's Bay Plus V Neck 3/4 Sleeve T-Shirt $11.19,
    # Biolage Color Last Shampoo 33.8 oz. $45.00,
    # Ambrielle Super Soft Full Coverage Underwire Bra $25.76,
    # St. John's Bay Universal ... Flat Front Pant $22.39,
    # Regal Home Diamond Embossed ... Blackout Set of 2 Curtain Panel $20.99.
    judge.check("answer_item_count", contains_count(answer, 6),
                "expected 6 saved wish-list items")
    judge.check("answer_item_one", contains_phrase(answer, "Crew Neck Short Sleeve T-Shirt")
                and contains_amount(answer, 11.20),
                "expected the SJB crew neck t-shirt at $11.20 (rendered $11.2)")
    judge.check("answer_item_two", contains_all(answer, ["Plus V Neck 3/4 Sleeve T-Shirt", "11.19"]),
                "expected the SJB plus v-neck t-shirt at $11.19")
    judge.check("answer_item_three", contains_phrase(answer, "Biolage Color Last Shampoo")
                and contains_amount(answer, 45.00),
                "expected the Biolage shampoo at $45.00 (rendered $45)")
    judge.check("answer_item_four", contains_all(answer, ["Ambrielle", "25.76"]),
                "expected the Ambrielle bra at $25.76")
    judge.check("answer_item_five", contains_all(answer, ["Flat Front Pant", "22.39"]),
                "expected the SJB flat front pant at $22.39")
    judge.check("answer_item_six", contains_all(answer, ["Diamond Embossed", "20.99"]),
                "expected the Regal Home blackout curtain set at $20.99")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
