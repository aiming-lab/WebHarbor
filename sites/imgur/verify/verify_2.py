#!/usr/bin/env python3
"""Verify the 'Ninja training' gallery report in Imgur--2."""


from verify_lib import (Judge, answer_has_klabel, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Imgur--2"
GALLERY_PATH = "/gallery/ninja-training-cedy3bN"  # 'Ninja training' (seed posts row cedy3bN)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the search must have been run and the matching post opened.
    judge.check("ran_ninja_training_search", navigated_search_with(traj, ["ninja", "training"]),
                "required /search?q=ninja+training")
    check_visited_path(judge, traj, "visited_ninja_training_gallery", GALLERY_PATH)
    # Frozen ground truth (seed DB, posts row cedy3bN): view_count 191658 (rendered
    # '192K Views'), author DOcelot1, platform android (rendered 'via Android').
    judge.check("answer_view_count_klabel", answer_has_klabel(answer, 191658),
                "expected the view count as rendered: 192K")
    judge.check("answer_author_username", contains_phrase(answer, "DOcelot1"),
                "expected the author username 'DOcelot1'")
    judge.check("answer_platform_label", contains_phrase(answer, "Android"),
                "expected the 'via Android' platform label")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
