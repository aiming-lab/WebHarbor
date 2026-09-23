#!/usr/bin/env python3
"""Verify the User Submitted feed report in Imgur--1."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_to_path_with_params,
                        run_verifier)

TASK_ID = "Imgur--1"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the feed must have been switched to USER SUBMITTED.
    judge.check("visited_user_submitted_feed",
                navigated_to_path_with_params(traj, "/", {"section": "user_sub"}),
                "required /?section=user_sub")
    # Frozen ground truth (seed DB): first User Submitted card (newest first) is
    # '"Grassley maintains one of the highest levels of loyalty to the Trump legislative
    #  agenda in the Senate".....I think you share a lot of the blame' (Jn4BLYU, 6 points).
    judge.check("answer_first_card_title_head",
                contains_phrase(answer, "Grassley maintains one of the highest levels of loyalty "
                                        "to the Trump legislative agenda in the Senate"),
                "expected the head of the first card title")
    judge.check("answer_first_card_title_tail",
                contains_phrase(answer, "I think you share a lot of the blame"),
                "expected the tail of the first card title")
    judge.check("answer_first_card_score", contains_count(answer, 6),
                "expected the score 6 displayed on the first card")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
