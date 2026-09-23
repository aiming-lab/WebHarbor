#!/usr/bin/env python3
"""Verify LandWatch--12 — carol.d@test.com removes the Montana saved search.

Ground truth (frozen seed): carol starts with 2 saved searches
('Farms and Ranches in Tennessee', 'Montana Land for Sale'); after removing
the Montana one, 1 remains, named 'Farms and Ranches in Tennessee'.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer,
                        run_verifier, table_delta)

TASK_ID = "LandWatch--12"
CAROL_EMAIL = "carol.d@test.com"
REMOVED_NAME = "Montana Land for Sale"
REMAINING_NAME = "Farms and Ranches in Tennessee"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL_EMAIL)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "saved_searches"})
    delta = table_delta(initial_db, after_db, "saved_searches")
    judge.check("exactly_montana_search_removed",
                len(delta["removed"]) == 1 and len(delta["added"]) == 0
                and len(delta["changed"]) == 0 and delta["removed"][0][2] == REMOVED_NAME,
                f"saved_searches delta={delta!r}")
    judge.check("answer_remaining_count", contains_count(answer, 1),
                "expected 1 saved search remaining")
    judge.check("answer_remaining_name", contains_phrase(answer, REMAINING_NAME),
                f"expected the remaining search {REMAINING_NAME!r}")
    judge.check("answer_does_not_claim_montana_remaining",
                not contains_phrase(answer, REMOVED_NAME),
                "the removed 'Montana Land for Sale' search must not be reported as remaining")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
