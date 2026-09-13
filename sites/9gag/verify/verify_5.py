#!/usr/bin/env python3
"""Verify 9GAG--5: browse Sports -> grandmother marathon post -> meeting kilometre + flag colour (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_trajectory_identity,
    check_visited_path, contains_all, contains_count, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--5"
INTEREST_PATH = "/interest/sports"
DETAIL_SLUGS = ("grandmother-finishes-her-first-marathon-at-seventy-two-15",
                "community-remix-5-grandmother-finishes-her-first-marathon-at-seventy-two-50")
KILOMETRE = 38
COLOUR = "orange"
QUESTION = "At which kilometer did her family meet her, and what color were their flags?"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_sports_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_kilometre", contains_count(answer, KILOMETRE), f"expected={KILOMETRE!r}, answer={answer!r}")
    judge.check("answer_has_flag_colour", contains_all(answer, (COLOUR,)), f"expected={COLOUR!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "kilometer 38; handmade orange flags", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
