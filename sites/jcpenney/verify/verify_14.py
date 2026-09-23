#!/usr/bin/env python3
"""Verify JCPenney--14."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--14"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_coupons_page", "/m/jcpenney-coupons")
    # Frozen ground truth (seed DB, coupons table): SAVE30 (Extra 30% off, through
    # Sept. 27, 2026), AUTUMN (Fall savings, Oct. 7, 2026), WATCH20 (extra 20% off,
    # Sept. 27, 2026), BRIDE40 (extra 40% off, Sept. 27, 2026), GOSHOP15 ($10 off your
    # $50 purchase, Oct. 15, 2026), SNEAK25 (Extra 25% off shoes, Oct. 5, 2026).
    # Longest-valid coupon: GOSHOP15.
    judge.check("answer_lists_all_six_codes",
                contains_all(answer, ["SAVE30", "AUTUMN", "WATCH20", "BRIDE40", "GOSHOP15", "SNEAK25"]),
                "expected all six coupon codes")
    judge.check("answer_save30", contains_all(answer, ["SAVE30", "30% off", "Sept. 27, 2026"]),
                "expected SAVE30 = Extra 30% off through Sept. 27, 2026")
    judge.check("answer_autumn", contains_all(answer, ["AUTUMN", "Oct. 7, 2026"]),
                "expected AUTUMN valid through Oct. 7, 2026")
    judge.check("answer_watch20", contains_all(answer, ["WATCH20", "20% off"]),
                "expected WATCH20 = extra 20% off")
    judge.check("answer_bride40", contains_all(answer, ["BRIDE40", "40% off"]),
                "expected BRIDE40 = extra 40% off")
    judge.check("answer_goshop15", contains_all(answer, ["GOSHOP15", "$10 off", "Oct. 15, 2026"]),
                "expected GOSHOP15 = $10 off your $50 purchase through Oct. 15, 2026")
    judge.check("answer_sneak25", contains_all(answer, ["SNEAK25", "25% off shoes", "Oct. 5, 2026"]),
                "expected SNEAK25 = Extra 25% off shoes through Oct. 5, 2026")
    judge.check("answer_longest_valid", contains_all(answer, ["GOSHOP15", "longest"]),
                "expected GOSHOP15 named as valid the longest")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
