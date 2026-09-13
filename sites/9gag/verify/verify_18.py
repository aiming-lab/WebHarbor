#!/usr/bin/env python3
"""Verify 9GAG--18: Alice logs in, opens Saved and removes the ORIGINAL solar camping post from her collection (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_only_tables_changed, check_paths_in_order, check_signed_in_as, check_trajectory_identity,
    check_visited_path, post_by_slug, run_verifier, saved_post_ids, table_delta, user_id_for_email,
)

TASK_ID = "9GAG--18"
EMAIL, USERNAME = "alice.j@test.com", "alice_j"
DETAIL_SLUG = "solar-powered-camping-setup-survives-a-rainy-weekend-11"  # seeded in Alice's saved collection


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    post = post_by_slug(initial_db, DETAIL_SLUG)
    judge.check("seed_has_target_post", bool(post), f"slug={DETAIL_SLUG!r}")
    post_id = int(post["id"]) if post else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_saved_collection", "/saved")
    check_paths_in_order(judge, traj, "workflow_login_before_saved", [("/login", {}), ("/saved", {})])
    judge.check("initial_state_requires_action", post_id in saved_post_ids(initial_db, user_id),
                f"post_id={post_id} saved initially for user {user_id}? {post_id in saved_post_ids(initial_db, user_id)}")
    delta = table_delta(initial_db, after_db, "saved_post")
    exact = (len(delta["removed"]) == 1 and not delta["added"] and not delta["changed"]
             and int(delta["removed"][0][1]) == user_id and int(delta["removed"][0][2]) == post_id)
    judge.check("saved_post_exact_delta", exact, f"expected one removed row (user_id={user_id}, post_id={post_id}); delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("saved_post",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
