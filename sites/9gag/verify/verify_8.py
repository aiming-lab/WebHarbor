#!/usr/bin/env python3
"""Verify 9GAG--8: search rain-delay concert -> the street-musician post -> platform number (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_search_visited,
    check_trajectory_identity, contains_count, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--8"
SEARCH_TOKENS = ("rain", "delay", "concert", "musician", "street", "platform", "chorus")
# The original and its "Community remix 12" clone (id 57) carry the identical description, so either
# detail page answers the question. Requiring the original would fail a correct answer on a hidden
# provenance rule; provenance is only enforced where it changes the graded outcome (9, 10-13, 18, 19).
DETAIL_SLUGS = ("street-musician-turns-a-rain-delay-into-a-concert-22",
                "community-remix-12-street-musician-turns-a-rain-delay-into-a-concert-57")
PLATFORM = 7
QUESTION = "Report the platform number where commuters joined the chorus."


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_platform_number", contains_count(answer, PLATFORM), f"expected={PLATFORM!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "platform seven", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
