#!/usr/bin/env python3
"""Verify the Learning Channel top-comment report in Imgur--3."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--3"
GALLERY_PATH = "/gallery/learning-channel-presents-bDO7HlN"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: comments sorted by Best render only on the gallery page.
    check_visited_path(judge, traj, "visited_learning_channel_gallery", GALLERY_PATH)
    # Frozen ground truth (seed DB): Best-sorted top comment on bDO7HlN is by
    # LitterBoxKing (46 points): 'And assholes of any age who carelessly tell you to
    # "just get a different job".' — the first eight words are
    # 'And assholes of any age who carelessly tell'.
    judge.check("answer_top_comment_author", contains_phrase(answer, "LitterBoxKing"),
                "expected the top comment author 'LitterBoxKing'")
    judge.check("answer_top_comment_points", contains_count(answer, 46),
                "expected the top comment's 46 points")
    judge.check("answer_top_comment_first_eight_words",
                contains_phrase(answer, "And assholes of any age who carelessly tell"),
                "expected the first eight words of the comment")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
