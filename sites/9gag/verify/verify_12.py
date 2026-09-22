#!/usr/bin/env python3
"""Verify 9GAG--12: Bob logs in, finds the ORIGINAL humming-bridge post in Science & Tech and posts an exact comment (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_detail_visited, check_only_tables_changed, check_paths_in_order, check_post_counter_delta,
    check_signed_in_as, check_trajectory_identity, check_visited_path, normalize_text, post_by_slug,
    run_verifier, table_delta, user_id_for_email,
)

TASK_ID = "9GAG--12"
EMAIL, USERNAME = "bob.c@test.com", "bob_c"
INTEREST_PATH = "/interest/science"
DETAIL_SLUG = "an-engineer-explains-why-this-bridge-hums-in-the-wind-19"  # the original, not the remix clone (id 54)
COMMENT = "Resonance makes ordinary structures fascinating."


def _same_comment(body):
    return normalize_text(body).rstrip(".") == normalize_text(COMMENT).rstrip(".")


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    post = post_by_slug(initial_db, DETAIL_SLUG)
    judge.check("seed_has_target_post", bool(post), f"slug={DETAIL_SLUG!r}")
    post_id = int(post["id"]) if post else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_science_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUG, name="visited_original_post_detail")
    check_paths_in_order(judge, traj, "workflow_login_browse_detail",
                         [("/login", {}), (INTEREST_PATH, {}), (f"/gag/{DETAIL_SLUG}", {})])
    delta = table_delta(initial_db, after_db, "comment")
    added = delta["added"]
    exact = (len(added) == 1 and not delta["removed"] and not delta["changed"]
             and int(added[0][1]) == post_id and int(added[0][2]) == user_id and _same_comment(added[0][3]))
    judge.check("comment_exact_delta", exact,
                f"expected one added comment (post_id={post_id}, user_id={user_id}, body={COMMENT!r}); delta={delta!r}")
    check_post_counter_delta(judge, initial_db, after_db, post_id, comment_count=1)
    check_only_tables_changed(judge, initial_db, after_db, allowed=("comment", "post"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
