#!/usr/bin/env python3
"""Verify 9GAG--10: Alice logs in, searches the lighthouse office post, opens the ORIGINAL and saves it (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_detail_visited, check_only_tables_changed, check_paths_in_order, check_search_visited,
    check_signed_in_as, check_trajectory_identity, post_by_slug, run_verifier, saved_post_ids, table_delta,
    user_id_for_email,
)

TASK_ID = "9GAG--10"
EMAIL, USERNAME = "alice.j@test.com", "alice_j"
SEARCH_TOKENS = ("lighthouse", "lighthouses", "office", "offices", "ocean")
DETAIL_SLUG = "tiny-lighthouse-office-with-the-best-ocean-view-12"  # the original, not the remix clone (id 47)


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    post = post_by_slug(initial_db, DETAIL_SLUG)
    judge.check("seed_has_target_post", bool(post), f"slug={DETAIL_SLUG!r}")
    post_id = int(post["id"]) if post else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUG, name="visited_original_post_detail")
    check_paths_in_order(judge, traj, "workflow_login_before_save", [("/login", {}), (f"/gag/{DETAIL_SLUG}", {})])
    judge.check("initial_state_requires_action", post_id not in saved_post_ids(initial_db, user_id),
                f"post_id={post_id} already saved initially? {post_id in saved_post_ids(initial_db, user_id)}")
    delta = table_delta(initial_db, after_db, "saved_post")
    exact = (len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"]
             and int(delta["added"][0][1]) == user_id and int(delta["added"][0][2]) == post_id)
    judge.check("saved_post_exact_delta", exact, f"expected one added row (user_id={user_id}, post_id={post_id}); delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("saved_post",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
