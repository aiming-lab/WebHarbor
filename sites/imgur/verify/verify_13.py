#!/usr/bin/env python3
"""Verify the two Mars-posts comparison in Imgur--13."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Imgur--13"
NASA_PATH = "/gallery/nasa-has-released-these-new-photos-from-surface-of-mars-ohbze3l"
NEWLY_PATH = "/gallery/newly-released-photos-from-surface-of-mars-released-by-nasa-sfxGceL"
# Frozen ground truth (seed DB): ohbze3l 'NASA has released these new photos from the
# surface of Mars' carries 3 stacked images; sfxGceL 'Newly released photos from the
# surface of Mars, released by NASA' carries 2; the larger one's author is MyNameGifOreilly.


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("ran_surface_of_mars_search", navigated_search_with(traj, ["surface", "mars"]),
                "required /search?q=surface+of+mars")
    check_visited_path(judge, traj, "visited_nasa_mars_gallery", NASA_PATH)
    check_visited_path(judge, traj, "visited_newly_mars_gallery", NEWLY_PATH)
    judge.check("answer_larger_image_count", contains_count(answer, 3),
                "expected the larger album's 3 images")
    judge.check("answer_smaller_image_count", contains_count(answer, 2),
                "expected the smaller album's 2 images")
    judge.check("answer_larger_author", contains_phrase(answer, "MyNameGifOreilly"),
                "expected the larger album's author 'MyNameGifOreilly'")
    judge.check("answer_names_nasa_post",
                contains_phrase(answer, "NASA has released these new photos"),
                "expected the NASA post title")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
