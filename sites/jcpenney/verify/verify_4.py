#!/usr/bin/env python3
"""Verify JCPenney--4."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sheet_set_product",
                       "/p/casual-comfort-premium-ultra-soft-microfiber-wrinkle-free-6-piece-sheet-set/ppr5007323303")
    # Frozen ground truth (seed DB, ppid ppr5007323303, INCLUDED spec):
    # 1 Fitted-Sheet - 39x75-Inch, 1 Flat-Sheet - 66x96-Inch, 2 Pillowcase - 30x20-Inch;
    # features: Fade Resistant, Wrinkle Free, Hypoallergenic, Antimicrobial.
    judge.check("answer_fitted_sheet", contains_all(answer, ["fitted", "39x75"]),
                "expected 1 Fitted-Sheet - 39x75-Inch")
    judge.check("answer_flat_sheet", contains_all(answer, ["flat", "66x96"]),
                "expected 1 Flat-Sheet - 66x96-Inch")
    judge.check("answer_pillowcases", contains_all(answer, ["2 pillowcase", "30x20"]),
                "expected 2 Pillowcase - 30x20-Inch")
    judge.check("answer_features", contains_all(answer, ["Fade Resistant", "Wrinkle Free",
                                                        "Hypoallergenic", "Antimicrobial"]),
                "expected the four called-out features")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
