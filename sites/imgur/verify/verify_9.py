#!/usr/bin/env python3
"""Verify the Welfare-Queens downvote flow in Imgur--9."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        final_answer, run_verifier, table_delta, vote_row)

TASK_ID = "Imgur--9"
DAVID_EMAIL = "david.k@test.com"
DAVID_USER_ID = 990000004
GALLERY_PATH = "/gallery/welfare-queens-looking-handouts-w29p1QE"
POST_ID = "w29p1QE"
# Frozen ground truth (seed DB): david_k already carries a seeded +1 vote on w29p1QE
# (point_count 1124 -> displayed 1125 before the click); downvoting flips the vote to
# -1 and the vote box renders 1123.


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID_EMAIL, "david_k")
    check_visited_path(judge, traj, "visited_welfare_queens_gallery", GALLERY_PATH)
    # DB after-state: only the votes table changes; david's seeded +1 row on w29p1QE
    # becomes -1.
    check_only_tables_changed(judge, initial_db, after_db, {"votes"})
    delta = table_delta(initial_db, after_db, "votes")
    judge.check("exactly_one_vote_row_changed",
                delta["added"] == [] and delta["removed"] == [] and len(delta["changed"]) == 1,
                f"votes delta={delta!r}")
    before_row = vote_row(initial_db, DAVID_USER_ID, POST_ID)
    after_row = vote_row(after_db, DAVID_USER_ID, POST_ID)
    judge.check("vote_flipped_plus1_to_minus1",
                before_row is not None and before_row.get("value") == 1
                and after_row is not None and after_row.get("value") == -1,
                f"before={before_row!r}, after={after_row!r}")
    judge.check("answer_score_after_downvote", contains_count(answer, 1123),
                "expected the vote box to show 1123 after the downvote")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
