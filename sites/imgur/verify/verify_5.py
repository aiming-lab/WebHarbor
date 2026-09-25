#!/usr/bin/env python3
"""Verify alice's FAVORITES-tab report in Imgur--5."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        contains_all, contains_count, final_answer, navigated_to_path_with_params,
                        run_verifier)

TASK_ID = "Imgur--5"
ALICE_EMAIL = "alice.j@test.com"
ALICE_USERNAME = "alice_j"
# Frozen ground truth (seed DB, favorites of alice_j): 4 posts.
EXPECTED_TITLES = ["it's always the ones you most suspect",
                   "I knew it! Damn telescopes /s",
                   "The Learning Channel presents",
                   "nice"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL, ALICE_USERNAME)
    judge.check("visited_favorites_tab",
                navigated_to_path_with_params(traj, "/user/alice_j", {"tab": "favorites"}),
                "required /user/alice_j?tab=favorites")
    judge.check("answer_favorite_count", contains_count(answer, 4),
                "expected 4 favorited posts")
    judge.check("answer_lists_every_favorite_title",
                contains_all(answer, EXPECTED_TITLES),
                f"expected all four titles {EXPECTED_TITLES!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
