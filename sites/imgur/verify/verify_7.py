#!/usr/bin/env python3
"""Verify the favorite 'Ninja training' flow in Imgur--7."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_count, favorite_post_ids, final_answer,
                        navigated_to_path_with_params, run_verifier, table_delta)

TASK_ID = "Imgur--7"
BOB_EMAIL = "bob.c@test.com"
BOB_USER_ID = 990000002
GALLERY_PATH = "/gallery/ninja-training-cedy3bN"
NEW_FAVORITE_ID = "cedy3bN"  # 'Ninja training'
# Frozen ground truth (seed DB): bob_c favorites 4 seeded + cedy3bN = 5.
EXPECTED_AFTER = ["CiBxeDw", "UHKZByE", "cedy3bN", "kfoQCDQ", "tm29v05"]
EXPECTED_TITLES = ["Whine more, Piggy", "Also, reading a lot can do this to you",
                   "Ninja training", "Day 384 of posting Calvin and Hobbes Comics",
                   "BAMBOOZLED BY THE PINGER"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL, "bob_c")
    check_visited_path(judge, traj, "visited_ninja_training_gallery", GALLERY_PATH)
    judge.check("visited_favorites_tab_after_save",
                navigated_to_path_with_params(traj, "/user/bob_c", {"tab": "favorites"}),
                "required /user/bob_c?tab=favorites after the save")
    # DB after-state: exactly one favorites row added (bob -> cedy3bN), nothing else.
    check_only_tables_changed(judge, initial_db, after_db, {"favorites"})
    delta = table_delta(initial_db, after_db, "favorites")
    from verify_lib import row_dict
    added_rows = [row_dict(after_db, "favorites", row) for row in delta["added"]]
    added_pairs = [(int(r["user_id"]), str(r["post_id"])) for r in added_rows]
    judge.check("exactly_one_favorite_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0
                and added_pairs == [(BOB_USER_ID, NEW_FAVORITE_ID)],
                f"favorites delta={delta!r}")
    observed = favorite_post_ids(after_db, BOB_USER_ID)
    judge.check("favorites_after_save_match_expected",
                observed == EXPECTED_AFTER,
                f"expected {EXPECTED_AFTER!r}, observed {observed!r}")
    judge.check("answer_lists_every_favorite_title",
                contains_all(answer, EXPECTED_TITLES),
                f"expected all five titles {EXPECTED_TITLES!r}")
    judge.check("answer_new_total_count", contains_count(answer, 5),
                "expected the new total count 5")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
