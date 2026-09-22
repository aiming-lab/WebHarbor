#!/usr/bin/env python3
"""Verify 9GAG--19: David logs in, compares three ORIGINAL Science & Tech posts by their stated numbers, saves the greatest (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_detail_visited, check_only_tables_changed, check_paths_in_order, check_signed_in_as,
    check_trajectory_identity, check_visited_path, post_by_slug, run_verifier, saved_post_ids, table_delta,
    user_id_for_email,
)

TASK_ID = "9GAG--19"
EMAIL, USERNAME = "david.k@test.com", "david_k"
INTEREST_PATH = "/interest/science"
# The comparison values live ONLY in the detail descriptions, so every detail page must be opened.
COMPARED = {
    "solar-powered-camping-setup-survives-a-rainy-weekend-11": 120,   # 120-watt panel
    "an-engineer-explains-why-this-bridge-hums-in-the-wind-19": 440,  # 440 hertz
    "students-launch-a-weather-balloon-with-a-tiny-rubber-duck-25": 27,  # 27 kilometers
}
WINNER_SLUG = "an-engineer-explains-why-this-bridge-hums-in-the-wind-19"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_compared_posts", all(post_by_slug(initial_db, s) for s in COMPARED), f"slugs={list(COMPARED)!r}")
    winner = post_by_slug(initial_db, WINNER_SLUG)
    post_id = int(winner["id"]) if winner else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_science_interest_feed", INTEREST_PATH)
    for slug in COMPARED:
        check_detail_visited(judge, traj, slug, name=f"visited_compared_detail_{slug.rsplit('-', 1)[1]}")
    check_paths_in_order(judge, traj, "workflow_login_before_browse", [("/login", {}), (INTEREST_PATH, {})])
    judge.check("initial_state_requires_action", post_id not in saved_post_ids(initial_db, user_id),
                f"post_id={post_id} already saved initially? {post_id in saved_post_ids(initial_db, user_id)}")
    delta = table_delta(initial_db, after_db, "saved_post")
    exact = (len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"]
             and int(delta["added"][0][1]) == user_id and int(delta["added"][0][2]) == post_id)
    judge.check("saved_post_exact_delta", exact,
                f"expected one added row (user_id={user_id}, post_id={post_id} = the greatest stated number); delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("saved_post",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
