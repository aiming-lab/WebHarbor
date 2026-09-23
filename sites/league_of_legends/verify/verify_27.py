#!/usr/bin/env python3
"""Verify League of Legends--27: How To Play lanes — 'the dynamite of the team'."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_phrase,
                        final_answer, navigated_to_path, run_verifier)

TASK_ID = "League of Legends--27"
# Frozen ground truth (how_to_play.html, Choose Your Lane > Bot Lane):
# "Bot lane champions are the dynamite of the team. As precious cargo, they need to be
# protected early on before amassing enough gold and experience to carry the team to
# victory."
LANE = "Bot Lane"
NEED = ["protected early on", "gold and experience"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_how_to_play", navigated_to_path(traj, "/how-to-play"),
                "required: /how-to-play/")
    judge.check("answer_lane", contains_phrase(answer, LANE),
                f"expected the lane {LANE!r}")
    judge.check("answer_dynamite_phrase", contains_phrase(answer, "dynamite"),
                "expected the quoted phrase 'the dynamite of the team'")
    missing = [f for f in NEED if not contains_phrase(answer, f)]
    judge.check("answer_needs_early", not missing,
                f"expected the early-game needs {NEED!r}; missing={missing!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
