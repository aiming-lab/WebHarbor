#!/usr/bin/env python3
"""Verify the aww tag-page report in Imgur--11."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--11"
TAG_PATH = "/t/aww"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_aww_tag_page", TAG_PATH)
    # Frozen ground truth (seed DB, tags row aww): total_items 691064, description
    # 'The cutest and most adorable things on the internet'; POPULAR-sorted first card
    # is 'The Purple Crayon [OC]' (b8eXzGz).
    judge.check("answer_tag_post_count", contains_count(answer, 691064),
                "expected 691,064 posts in the tag header")
    judge.check("answer_tag_description",
                contains_phrase(answer, "The cutest and most adorable things on the internet"),
                "expected the tag description line")
    judge.check("answer_first_card_title", contains_phrase(answer, "The Purple Crayon"),
                "expected the first post card title 'The Purple Crayon [OC]'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
