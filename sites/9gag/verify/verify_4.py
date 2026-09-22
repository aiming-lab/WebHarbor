#!/usr/bin/env python3
"""Verify 9GAG--4: search community library -> night-shift workers post -> cabinet colour + restock time (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_search_visited,
    check_trajectory_identity, contains_all, contains_clock_time, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--4"
SEARCH_TOKENS = ("library", "libraries", "community", "night", "shift", "cabinet")
DETAIL_SLUGS = ("neighborhood-builds-a-miniature-library-for-night-shift-workers-18",
                "community-remix-8-neighborhood-builds-a-miniature-library-for-night-shift-workers-53")
COLOUR = "blue"
DAY = "Thursday"
TIME = "6 am"
QUESTION = "What color is the cabinet, and exactly when is it restocked?"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_cabinet_colour", contains_all(answer, (COLOUR,)), f"expected={COLOUR!r}, answer={answer!r}")
    judge.check("answer_has_restock_day", contains_all(answer, (DAY,)), f"expected={DAY!r}, answer={answer!r}")
    judge.check("answer_has_restock_time", contains_clock_time(answer, TIME), f"expected={TIME!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "blue cabinet; restocked every Thursday at 6 a.m.", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
