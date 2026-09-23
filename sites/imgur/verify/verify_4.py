#!/usr/bin/env python3
"""Verify the Funny tag-page report in Imgur--4."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--4"
TAG_PATH = "/t/funny"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_funny_tag_page", TAG_PATH)
    # Frozen ground truth (seed DB, tags row funny): total_items 2303068, description
    # 'LOLs, ROFLs, LMAOs'; POPULAR-sorted first card is 'The Learning Channel presents...'.
    judge.check("answer_tag_post_count", contains_count(answer, 2303068),
                "expected 2,303,068 posts in the tag header")
    judge.check("answer_tag_description",
                contains_phrase(answer, "LOLs, ROFLs, LMAOs")
                or contains_phrase(answer, "LOLs ROFLs LMAOs"),
                "expected the tag description line")
    judge.check("answer_first_card_title", contains_phrase(answer, "The Learning Channel presents"),
                "expected the first post card title")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
