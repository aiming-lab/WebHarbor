#!/usr/bin/env python3
"""Verify 9GAG--2: search solar camping -> rainy-weekend setup -> panel wattage + controller protection (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_search_visited,
    check_trajectory_identity, contains_count, contains_phrase, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--2"
SEARCH_TOKENS = ("solar", "camping", "camp", "rainy", "panel")
DETAIL_SLUGS = ("solar-powered-camping-setup-survives-a-rainy-weekend-11",
                "community-remix-1-solar-powered-camping-setup-survives-a-rainy-weekend-46")
WATTS = 120
PROTECTION = "lunch box"
QUESTION = "What wattage was its folding panel, and what protected the controller from water?"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_panel_wattage", contains_count(answer, WATTS), f"expected={WATTS!r}, answer={answer!r}")
    judge.check("answer_has_controller_protection", contains_phrase(answer, PROTECTION), f"expected={PROTECTION!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "120-watt folding panel; controller kept in a waterproof lunch box", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
