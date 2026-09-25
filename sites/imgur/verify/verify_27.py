#!/usr/bin/env python3
"""Verify the anime-tag follow flow in Imgur--27."""

import re

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, final_answer, follow_tag_pairs, norm, run_verifier,
                        table_delta)

TASK_ID = "Imgur--27"
CAROL_EMAIL = "carol.d@test.com"
CAROL_USER_ID = 990000003
TAG_PATH = "/t/anime"
TAG_NAME = "anime"
TAG_TOTAL_ITEMS = 103725
TAG_DESCRIPTION = "There's OVER 9,000 Posts here!"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL_EMAIL, "carol_d")
    check_visited_path(judge, traj, "visited_anime_tag_page", TAG_PATH)
    # DB after-state: exactly one follow_tag row added (carol -> anime).
    check_only_tables_changed(judge, initial_db, after_db, {"follow_tag"})
    delta = table_delta(initial_db, after_db, "follow_tag")
    judge.check("exactly_one_follow_tag_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"follow_tag delta={delta!r}")
    observed = follow_tag_pairs(after_db, CAROL_USER_ID)
    expected = sorted(set(follow_tag_pairs(initial_db, CAROL_USER_ID)) | {TAG_NAME})
    judge.check("carol_follows_anime_after_flow", observed == expected,
                f"expected {expected!r}, observed {observed!r}")
    # Frozen ground truth: button flips to FOLLOWING; tag header shows 103,725 posts and
    # the description line 'There's OVER 9,000 Posts here!'.
    judge.check("answer_button_new_label", contains_phrase(answer, "FOLLOWING"),
                "expected the button's new label FOLLOWING")
    judge.check("answer_tag_post_count", contains_count(answer, TAG_TOTAL_ITEMS),
                f"expected {TAG_TOTAL_ITEMS:,} posts in the tag header")
    judge.check("answer_tag_description",
                bool(re.search(r"over\s*9,?000\s*posts\s*here", norm(answer))),
                f"expected the tag description {TAG_DESCRIPTION!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
