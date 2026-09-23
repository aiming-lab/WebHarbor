#!/usr/bin/env python3
"""Verify the 'The Real MVP!' gallery report in Imgur--0."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--0"
GALLERY_PATH = "/gallery/real-mvp-4SmuGpb"  # 'The Real MVP!' (seed posts row 4SmuGpb)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the task names the homepage feed and the post page; the score box,
    # comments header and author line are rendered only on the gallery page.
    check_visited_path(judge, traj, "visited_homepage_feed", "/")
    check_visited_path(judge, traj, "visited_real_mvp_gallery", GALLERY_PATH)
    # Frozen ground truth (seed DB, posts row 4SmuGpb): point_count 1425,
    # comment_count 230, author username Luvlyquants.
    judge.check("answer_vote_score", contains_count(answer, 1425), "expected score 1425 in the vote box")
    judge.check("answer_comments_header_count", contains_count(answer, 230),
                "expected 230 COMMENTS in the comments header")
    judge.check("answer_author_username", contains_phrase(answer, "Luvlyquants"),
                "expected the author username 'Luvlyquants'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
