#!/usr/bin/env python3
"""Verify the Arcade-page report in Imgur--23."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "Imgur--23"
ARCADE_PATH = "/arcade"
MOVED_MESSAGE = "Imgur arcade has moved to Lil Snack!"
GREEN_BUTTON_LABEL = "Sign in or Sign up to play all the games"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_arcade_page", ARCADE_PATH)
    # Frozen ground truth (templates/arcade.html): the hero line
    # 'Imgur arcade has moved to Lil Snack!' and the green top CTA
    # 'Sign in or Sign up to play all the games'.
    judge.check("answer_moved_message", contains_phrase(answer, MOVED_MESSAGE),
                f"expected the exact moved message {MOVED_MESSAGE!r}")
    judge.check("answer_green_button_label", contains_phrase(answer, GREEN_BUTTON_LABEL),
                f"expected the green button label {GREEN_BUTTON_LABEL!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
