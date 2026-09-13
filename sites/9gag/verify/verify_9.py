#!/usr/bin/env python3
"""Verify 9GAG--9: browse Animals & Pets, compare the three ORIGINAL posts' points -> open the winner -> animal name (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_trajectory_identity,
    check_visited_path, contains_all, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--9"
INTEREST_PATH = "/interest/animals"
CANDIDATES = {  # original posts only; the remix clones carry different point counts
    "rescue-cat-learns-the-sound-of-the-treat-drawer-13": 2506,
    "dog-refuses-to-leave-the-kayak-after-the-trip-ends-20": 3717,
    "a-fox-naps-on-the-same-garden-wall-every-afternoon-23": 4236,
}
WINNER_SLUG = "a-fox-naps-on-the-same-garden-wall-every-afternoon-23"
ANIMAL_NAME = "Copper"
QUESTION = "Which of the three original posts has the most points? Open it and report the animal's name."


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    seed_points = {s: (post_by_slug(initial_db, s) or {}).get("up_votes") for s in CANDIDATES}
    judge.check("seed_points_match_frozen_ground_truth", seed_points == CANDIDATES,
                f"expected={CANDIDATES!r}, observed={seed_points!r}")
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_animals_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, WINNER_SLUG, name="visited_winning_post_detail")
    judge.check("answer_has_animal_name", contains_all(answer, (ANIMAL_NAME,)), f"expected={ANIMAL_NAME!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "the garden-fox post (most points); the fox is named Copper", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
