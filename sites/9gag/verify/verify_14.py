#!/usr/bin/env python3
"""Verify 9GAG--14: David logs in, opens News, finds the 2009 press-conference post and reports it for Misinformation (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_detail_visited, check_only_tables_changed, check_paths_in_order, check_signed_in_as,
    check_trajectory_identity, check_visited_path, normalize_text, post_by_slug, run_verifier, table_delta,
    user_id_for_email,
)

TASK_ID = "9GAG--14"
EMAIL, USERNAME = "david.k@test.com", "david_k"
NEWS_PATH = "/news"
DETAIL_SLUG = "a-mysterious-press-conference-moment-from-2009-6"
REASON = "Misinformation"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    post = post_by_slug(initial_db, DETAIL_SLUG)
    judge.check("seed_has_target_post", bool(post), f"slug={DETAIL_SLUG!r}")
    post_id = int(post["id"]) if post else -1
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_news_feed", NEWS_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUG)
    check_visited_path(judge, traj, "visited_report_form", f"/gag/{DETAIL_SLUG}/report")
    check_paths_in_order(judge, traj, "workflow_login_news_detail_report",
                         [("/login", {}), (NEWS_PATH, {}), (f"/gag/{DETAIL_SLUG}", {}), (f"/gag/{DETAIL_SLUG}/report", {})])
    delta = table_delta(initial_db, after_db, "report")
    added = delta["added"]
    exact = (len(added) == 1 and not delta["removed"] and not delta["changed"]
             and int(added[0][1]) == user_id and int(added[0][2]) == post_id
             and normalize_text(added[0][3]) == normalize_text(REASON))
    judge.check("report_exact_delta", exact,
                f"expected one added report (user_id={user_id}, post_id={post_id}, reason={REASON!r}); delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("report",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
