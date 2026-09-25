#!/usr/bin/env python3
"""Verify the un-favorite flow and remaining-titles report in Imgur--6."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_count, favorite_post_ids, final_answer,
                        navigated_to_path_with_params, run_verifier, table_delta,
                        user_by_email)

TASK_ID = "Imgur--6"
ALICE_EMAIL = "alice.j@test.com"
ALICE_USER_ID = 990000001
GALLERY_PATH = "/gallery/learning-channel-presents-bDO7HlN"  # the baby-boomers post
REMOVED_POST_ID = "bDO7HlN"
# Frozen ground truth (seed DB): alice_j favorites 4 -> 3 after removing bDO7HlN.
REMAINING_POST_IDS = ["C8JgWDF", "CDupyGR", "ebGkkT0"]
REMAINING_TITLES = ["it's always the ones you most suspect",
                    "I knew it! Damn telescopes /s",
                    "nice"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL, "alice_j")
    check_visited_path(judge, traj, "visited_boomers_post_gallery", GALLERY_PATH)
    judge.check("visited_favorites_tab_after_removal",
                navigated_to_path_with_params(traj, "/user/alice_j", {"tab": "favorites"}),
                "required /user/alice_j?tab=favorites after the removal")
    # DB after-state: exactly one favorites row removed (alice -> bDO7HlN), nothing else.
    check_only_tables_changed(judge, initial_db, after_db, {"favorites"})
    delta = table_delta(initial_db, after_db, "favorites")
    from verify_lib import row_dict
    removed_rows = [row_dict(after_db, "favorites", row) for row in delta["removed"]]
    removed_pairs = [(int(r["user_id"]), str(r["post_id"])) for r in removed_rows]
    judge.check("exactly_one_favorite_removed",
                delta["added"] == [] and len(delta["removed"]) == 1 and len(delta["changed"]) == 0
                and removed_pairs == [(ALICE_USER_ID, REMOVED_POST_ID)],
                f"favorites delta={delta!r}")
    observed = favorite_post_ids(after_db, ALICE_USER_ID)
    judge.check("remaining_favorites_match_seed_minus_removed",
                observed == REMAINING_POST_IDS,
                f"expected remaining favorites {REMAINING_POST_IDS!r}, observed {observed!r}")
    # The four benchmark users keep their identity; user_by_email must resolve.
    judge.check("alice_still_registered", user_by_email(after_db, ALICE_EMAIL) is not None,
                "alice_j must still exist after the flow")
    judge.check("answer_lists_remaining_titles", contains_all(answer, REMAINING_TITLES),
                f"expected the remaining titles {REMAINING_TITLES!r}")
    judge.check("answer_remaining_count", contains_count(answer, 3),
                "expected 3 remaining favorites")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
