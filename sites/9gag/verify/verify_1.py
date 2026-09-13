#!/usr/bin/env python3
"""Verify 9GAG--1: search rescue cat -> treat-drawer post -> arrival month + days to learn (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_search_visited,
    check_trajectory_identity, contains_all, contains_count, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--1"
SEARCH_TOKENS = ("rescue", "cat", "cats", "treat", "drawer", "miso")
DETAIL_SLUGS = ("rescue-cat-learns-the-sound-of-the-treat-drawer-13",
                "community-remix-3-rescue-cat-learns-the-sound-of-the-treat-drawer-48")
MONTH = "February"
DAYS = 11
QUESTION = "Report the month Miso arrived at Harbor Paws and how many days the routine took to learn."


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_arrival_month", contains_all(answer, (MONTH,)), f"expected={MONTH!r}, answer={answer!r}")
    judge.check("answer_has_days_count", contains_count(answer, DAYS), f"expected={DAYS!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "arrived in February; learned the routine after eleven days", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
