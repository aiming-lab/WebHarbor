#!/usr/bin/env python3
"""Verify 9GAG--3: browse Science & Tech -> humming-bridge post -> frequency + resonating feature (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_trajectory_identity,
    check_visited_path, contains_any, contains_count, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--3"
INTEREST_PATH = "/interest/science"
DETAIL_SLUGS = ("an-engineer-explains-why-this-bridge-hums-in-the-wind-19",
                "community-remix-9-an-engineer-explains-why-this-bridge-hums-in-the-wind-54")
HERTZ = 440
FEATURE = ("railing", "railings")
QUESTION = "Report the frequency of the note and the bridge feature that produces it."


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_science_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_frequency_hertz", contains_count(answer, HERTZ), f"expected={HERTZ!r}, answer={answer!r}")
    judge.check("answer_has_resonating_feature", contains_any(answer, FEATURE), f"expected one of {FEATURE!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "near 440 hertz; produced by evenly spaced railings", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
