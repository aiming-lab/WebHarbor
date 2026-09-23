#!/usr/bin/env python3
"""Verify the top-two feed-scores comparison in Imgur--24.

Contract note: the task wording says 'visible on the first screen of the feed'. A
viewport cannot be graded deterministically (the number of visible masonry cards varies
with window size), so the verifier grades the contributor's own documented reading —
the FIRST PAGE of the Most Viral feed (the 60 posts before 'Load more posts'), whose
top two scores are 866 and 857. The reviewer flags the wording for a fix-round re-anchor
to 'first page'; the frozen numbers below do not change.
"""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--24"
TOP_TITLE_HEAD = "Wow... the press finally got tired of trump"
TOP_TITLE_TAIL = "the TV news networks weren't there providing mics and coverage"
SECOND_TITLE = "Let's goooo"
TOP_SCORE = 866
SECOND_SCORE = 857
DIFFERENCE = 9


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage_feed", "/")
    # Frozen ground truth (seed DB): first Most Viral page top two by point_count —
    # 866 'Wow... the press finally got tired of trump...' and 857 'Let's goooo!!!'.
    judge.check("answer_top_title_head", contains_phrase(answer, TOP_TITLE_HEAD),
                "expected the head of the highest-scored post title")
    judge.check("answer_top_title_tail", contains_phrase(answer, TOP_TITLE_TAIL),
                "expected the tail of the highest-scored post title")
    judge.check("answer_second_title", contains_phrase(answer, SECOND_TITLE),
                "expected the second post title 'Let's goooo!!!'")
    judge.check("answer_top_score", contains_count(answer, TOP_SCORE),
                f"expected the highest score {TOP_SCORE}")
    judge.check("answer_second_score", contains_count(answer, SECOND_SCORE),
                f"expected the second-highest score {SECOND_SCORE}")
    judge.check("answer_score_difference", contains_count(answer, DIFFERENCE),
                f"expected the difference {DIFFERENCE}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
