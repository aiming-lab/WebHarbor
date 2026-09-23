#!/usr/bin/env python3
"""Verify the GullahGullahIslander ABOUT-tab report in Imgur--26."""


from verify_lib import (Judge, answer_has_klabel, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase, final_answer,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Imgur--26"
PROFILE_PATH = "/user/GullahGullahIslander"
# Frozen ground truth (seed DB, users row GullahGullahIslander): reputation 2396949
# (hero '2,396,949 PTS'; ABOUT tab renders '2397K reputation points'),
# reputation_name LEGENDARY, 5 trophies displayed on the ABOUT tab.


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_gullah_about_tab",
                navigated_to_path_with_params(traj, PROFILE_PATH, {"tab": "about"}),
                "required /user/GullahGullahIslander?tab=about")
    judge.check("answer_reputation_points",
                contains_count(answer, 2396949) or answer_has_klabel(answer, 2396949),
                "expected 2,396,949 reputation points (or the ABOUT tab's 2397K rendering)")
    judge.check("answer_reputation_tier", contains_phrase(answer, "Legendary"),
                "expected the reputation tier LEGENDARY")
    judge.check("answer_trophy_count", contains_count(answer, 5),
                "expected 5 trophies on the ABOUT tab")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
