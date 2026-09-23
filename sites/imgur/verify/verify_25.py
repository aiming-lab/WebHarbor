#!/usr/bin/env python3
"""Verify the OnlyBiscuits gallery report in Imgur--25."""


from verify_lib import (Judge, answer_has_klabel, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase, final_answer,
                        navigated_search_with, run_verifier)

TASK_ID = "Imgur--25"
GALLERY_PATH = "/gallery/onlybiscuits-no-talk-KhxM5K2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("ran_onlybiscuits_search", navigated_search_with(traj, ["onlybiscuits"]),
                "required /search?q=onlybiscuits")
    check_visited_path(judge, traj, "visited_onlybiscuits_gallery", GALLERY_PATH)
    # Frozen ground truth (seed DB, posts row KhxM5K2): author PushPullMagnet, platform
    # desktop (rendered 'via Web'), view_count 61767 (rendered '61.8K'), point_count 587.
    judge.check("answer_author_username", contains_phrase(answer, "PushPullMagnet"),
                "expected the author username 'PushPullMagnet'")
    judge.check("answer_platform_label", contains_phrase(answer, "Web"),
                "expected the 'via Web' platform label")
    judge.check("answer_view_count_klabel", answer_has_klabel(answer, 61767),
                "expected the view count as rendered: 61.8K")
    judge.check("answer_post_score", contains_count(answer, 587),
                "expected 587 in the vote box")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
