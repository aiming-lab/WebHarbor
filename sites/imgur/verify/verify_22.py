#!/usr/bin/env python3
"""Verify the newest-sorted Real-MVP comment report in Imgur--22."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_to_path_with_params,
                        run_verifier)

TASK_ID = "Imgur--22"
GALLERY_PATH = "/gallery/real-mvp-4SmuGpb"
# Frozen ground truth (seed DB): with sort=new the first top-level comment on 4SmuGpb is
# david_k's 'Saved this one to my favorites folder.' (4 points, comment id 3000000005).


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the gallery page with sort=new (the 'new' link in the comments head).
    judge.check("visited_real_mvp_new_sort",
                navigated_to_path_with_params(traj, GALLERY_PATH, {"sort": "new"}),
                "required /gallery/real-mvp-4SmuGpb?sort=new")
    judge.check("answer_first_new_comment_author", contains_phrase(answer, "david_k"),
                "expected the first comment author 'david_k'")
    judge.check("answer_first_new_comment_text",
                contains_phrase(answer, "Saved this one to my favorites folder"),
                "expected the comment text 'Saved this one to my favorites folder.'")
    judge.check("answer_first_new_comment_points", contains_count(answer, 4),
                "expected the comment's 4 points")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
