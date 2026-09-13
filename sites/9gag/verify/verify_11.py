#!/usr/bin/env python3
"""Verify 9GAG--11: Carol logs in, browses Animals & Pets, opens the ORIGINAL kayak-dog post and upvotes it (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_detail_visited, check_only_tables_changed, check_paths_in_order, check_post_counter_delta,
    check_signed_in_as, check_trajectory_identity, check_visited_path, post_by_slug, run_verifier,
    table_delta, user_id_for_email, votes_for,
)

TASK_ID = "9GAG--11"
EMAIL, USERNAME = "carol.d@test.com", "carol_d"
INTEREST_PATH = "/interest/animals"
DETAIL_SLUG = "dog-refuses-to-leave-the-kayak-after-the-trip-ends-20"  # the original, not the remix clone (id 55)


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    post = post_by_slug(initial_db, DETAIL_SLUG)
    judge.check("seed_has_target_post", bool(post), f"slug={DETAIL_SLUG!r}")
    post_id = int(post["id"]) if post else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_animals_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUG, name="visited_original_post_detail")
    check_paths_in_order(judge, traj, "workflow_login_browse_detail",
                         [("/login", {}), (INTEREST_PATH, {}), (f"/gag/{DETAIL_SLUG}", {})])
    judge.check("initial_state_requires_action", post_id not in votes_for(initial_db, user_id),
                f"initial votes for user {user_id}: {votes_for(initial_db, user_id)!r}")
    delta = table_delta(initial_db, after_db, "vote")
    exact = (len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"]
             and int(delta["added"][0][1]) == user_id and int(delta["added"][0][2]) == post_id
             and int(delta["added"][0][3]) == 1)
    judge.check("vote_exact_delta", exact, f"expected one added upvote (user_id={user_id}, post_id={post_id}, value=1); delta={delta!r}")
    check_post_counter_delta(judge, initial_db, after_db, post_id, up_votes=1)
    check_only_tables_changed(judge, initial_db, after_db, allowed=("vote", "post"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
