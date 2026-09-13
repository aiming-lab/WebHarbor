#!/usr/bin/env python3
"""Verify 9GAG--7: browse Gaming -> transparent keyboard post -> switch type + case material (read-only).

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

TASK_ID = "9GAG--7"
INTEREST_PATH = "/interest/gaming"
DETAIL_SLUGS = ("mechanical-keyboard-made-entirely-from-transparent-parts-14",
                "community-remix-4-mechanical-keyboard-made-entirely-from-transparent-parts-49")
SWITCHES = ("silent", "tactile")
CASE = "acrylic"
QUESTION = "What kind of switches and what case material does it use?"


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_gaming_interest_feed", INTEREST_PATH)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_switch_type", contains_all(answer, SWITCHES), f"expected={SWITCHES!r}, answer={answer!r}")
    judge.check("answer_has_case_material", contains_all(answer, (CASE,)), f"expected={CASE!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "silent tactile switches; hand-polished acrylic case", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
