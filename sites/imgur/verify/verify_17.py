#!/usr/bin/env python3
"""Verify the HR-post author profile report in Imgur--17."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Imgur--17"
HR_GALLERY_PATH = "/gallery/you-only-like-hr-until-you-get-hired-GEQJDEQ"
PROFILE_PATH = "/user/svardfiska"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("ran_hr_post_search",
                navigated_search_with(traj, ["hr"]),
                "required a search that finds 'You only like HR until you get hired'")
    check_visited_path(judge, traj, "visited_hr_post_gallery", HR_GALLERY_PATH)
    check_visited_path(judge, traj, "visited_author_profile", PROFILE_PATH)
    # Frozen ground truth (seed DB): the post's author is svardfiska (reputation_name
    # GLORIOUS); their POSTS tab lists exactly 2 posts.
    judge.check("answer_author_username", contains_phrase(answer, "svardfiska"),
                "expected the author username 'svardfiska'")
    judge.check("answer_author_tier", contains_phrase(answer, "Glorious"),
                "expected the reputation tier GLORIOUS")
    judge.check("answer_posts_tab_count", contains_count(answer, 2),
                "expected 2 posts on the POSTS tab")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
