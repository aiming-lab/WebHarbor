#!/usr/bin/env python3
"""Verify LandWatch--10 — alice.j@test.com My LandWatch saved state.

Ground truth (frozen seed): 5 saved properties, 3 saved searches named
'Boerne, TX Land for Sale', 'Hunting Land under $250K', 'Texas Land for Sale'.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer,
                        run_verifier, table_delta)

TASK_ID = "LandWatch--10"
ALICE_EMAIL = "alice.j@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions"})
    delta = table_delta(initial_db, after_db, "sessions")
    judge.check("sessions_touch_only_alice",
                all(row[1] == 1 for row in delta["added"] + delta["removed"]),
                f"sessions delta={delta!r}")
    judge.check("answer_saved_properties_count", contains_count(answer, 5),
                "expected 5 saved properties")
    judge.check("answer_saved_searches_count", contains_count(answer, 3),
                "expected 3 saved searches")
    for name in ("Boerne, TX Land for Sale", "Hunting Land under $250K",
                 "Texas Land for Sale"):
        judge.check(f"answer_search_{name[:12].lower().replace(' ', '_')}",
                    contains_phrase(answer, name),
                    f"expected the saved search {name!r}")
    check_visited_path(judge, traj, "visited_account_page_after", "/account")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
