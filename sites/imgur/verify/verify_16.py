#!/usr/bin/env python3
"""Verify the tampacl ABOUT-tab report in Imgur--16."""


from verify_lib import (Judge, answer_has_klabel, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_date_phrase, contains_phrase,
                        final_answer, navigated_search_with, navigated_to_path_with_params,
                        run_verifier)

TASK_ID = "Imgur--16"
ANCHOR_GALLERY_PATH = "/gallery/cat-distribution-system-is-always-working-yR5molC"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the cat-distribution search, the post page, and tampacl's ABOUT tab.
    judge.check("ran_cat_distribution_search",
                navigated_search_with(traj, ["cat", "distribution"]),
                "required /search?q=cat+distribution")
    check_visited_path(judge, traj, "visited_cat_distribution_post", ANCHOR_GALLERY_PATH)
    judge.check("visited_tampacl_about_tab",
                navigated_to_path_with_params(traj, "/user/tampacl", {"tab": "about"}),
                "required /user/tampacl?tab=about")
    # Frozen ground truth (seed DB, users row tampacl): reputation 3727264 (hero
    # '3,727,264 PTS'; ABOUT tab renders it as '3727K reputation points'),
    # reputation_name LEGENDARY, joined 2015-12-22 -> 'Joined December 22, 2015'.
    judge.check("answer_reputation_points",
                contains_count(answer, 3727264) or answer_has_klabel(answer, 3727264),
                "expected 3,727,264 reputation points (or the ABOUT tab's 3727K rendering)")
    judge.check("answer_reputation_tier", contains_phrase(answer, "Legendary"),
                "expected the reputation tier LEGENDARY")
    judge.check("answer_join_date", contains_date_phrase(answer, "December 22, 2015"),
                "expected the join date 'Joined December 22, 2015'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
