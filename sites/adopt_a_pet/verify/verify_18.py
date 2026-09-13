#!/usr/bin/env python3
"""Verify AdoptAPet--18: Pet advice page -> titles of the paperwork, adoption-fee and
bringing-home-a-dog articles (read-only). Titles are page-specific strings; punctuation and
quoting differences are tolerated, wording is not.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, check_visited_path, contains_phrase_loose, final_answer, run_verifier,
)

TASK_ID = "AdoptAPet--18"
TITLES = [GT.BLOG_TITLES[0], GT.BLOG_TITLES[1], GT.BLOG_TITLES[2]]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_pet_advice", "/blog")
    for idx, title in enumerate(TITLES):
        judge.check(f"answer_has_title_{idx}", contains_phrase_loose(answer, title), f"expected={title!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
