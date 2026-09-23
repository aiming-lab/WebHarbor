#!/usr/bin/env python3
"""Verify LandWatch--16 — Florida + Waterfront property type.

Ground truth (frozen seed): Florida has exactly 1 waterfront land listing,
'Firefly Resorts- RV/Tiny Home' at $99,900. The reviewer notes the sidebar
Property Types links drop the state context (upstream preserves it as
/florida-land-for-sale/waterfront-property), so the state+type URL is the
required navigation.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--16"
FL_PATH = "/florida-land-for-sale"
FL_WATERFRONT_PATH = "/florida-land-for-sale/waterfront-property"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_florida_page", FL_PATH)
    check_visited_path(judge, traj, "visited_florida_waterfront_page", FL_WATERFRONT_PATH)
    judge.check("answer_florida_waterfront_count", contains_count(answer, 1),
                "expected 1 waterfront land listing in Florida")
    judge.check("answer_first_title", contains_phrase(answer, "Firefly Resorts"),
                "expected the first listing 'Firefly Resorts- RV/Tiny Home'")
    judge.check("answer_first_price", contains_money(answer, 99900),
                "expected the first listing price $99,900")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
