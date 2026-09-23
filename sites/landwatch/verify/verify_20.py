#!/usr/bin/env python3
"""Verify LandWatch--20 — david.k@test.com saved-properties listing (removal pending user choice).

Ground truth (frozen seed): david has exactly 6 saved properties: 'Three W
Trophy Ranch', '1,585-Acre Cattle Empire', 'Hunting Property Auction',
'Kentucky Trophy Hunt Auction', "Benton's Prime Land Auction", 'RRP Real
Estate Auction'. The task asks the agent to list them so the user can decide
which to remove; the gradeable deliverable is the complete list. Both an
await-instruction run (favorites unchanged) and an over-eager single removal
(exactly one favorite row gone) are accepted — see verify/README.md.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, run_verifier,
                        table_delta)

TASK_ID = "LandWatch--20"
DAVID_EMAIL = "david.k@test.com"
TITLES = ["Three W Trophy Ranch", "1,585-Acre Cattle Empire", "Hunting Property Auction",
          "Kentucky Trophy Hunt Auction", "Benton's Prime Land Auction",
          "RRP Real Estate Auction"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID_EMAIL)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "favorites"})
    delta = table_delta(initial_db, after_db, "favorites")
    unchanged = not delta["added"] and not delta["removed"] and not delta["changed"]
    one_removed = (not delta["added"] and not delta["changed"] and len(delta["removed"]) == 1)
    judge.check("favorites_unchanged_or_exactly_one_removed", unchanged or one_removed,
                f"favorites delta={delta!r} (0 or 1 removals accepted)")
    for i, title in enumerate(TITLES):
        key = title.lower()[:14].replace(" ", "_").replace("'", "")
        judge.check(f"answer_lists_favorite_{i}_{key}", contains_phrase(answer, title),
                    f"expected the saved property {title!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
