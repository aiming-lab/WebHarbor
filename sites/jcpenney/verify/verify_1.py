#!/usr/bin/env python3
"""Verify JCPenney--1."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_blackout_search", navigated_search(traj, "blackout curtain panel"),
                "required: search for blackout curtain panel")
    check_visited_path(judge, traj, "visited_max_blackout_product",
                       "/p/max-blackout-mystique-grommet-top-100-blackout-single-curtain-panel/ppr5007989193")
    # Frozen ground truth (seed DB, ppid ppr5007989193): sale $52.50 - $80.50,
    # struck-through original $80.77 - $123.85, 9 color swatches.
    judge.check("answer_product_name", contains_phrase(answer, "Max Blackout Mystique Grommet Top"),
                "expected the Max Blackout Mystique Grommet Top curtain panel")
    judge.check("answer_sale_price", contains_amount(answer, 52.50),
                "expected the sale price low end $52.50 (page shows $52.50 - $80.50)")
    judge.check("answer_original_price", contains_amount(answer, 80.77),
                "expected the struck-through original $80.77 (page shows $80.77 - $123.85)")
    judge.check("answer_swatch_count", contains_count(answer, 9),
                "expected 9 color options (swatches) on the product page")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
