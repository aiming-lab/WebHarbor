#!/usr/bin/env python3
"""Verify 9GAG--0: search lighthouse offices -> best-ocean-view post -> room width + desk material (read-only).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    advisory_llm_answer, check_detail_visited, check_read_only, check_search_visited,
    check_trajectory_identity, contains_all, contains_decimal, final_answer, post_by_slug, run_verifier,
)

TASK_ID = "9GAG--0"
SEARCH_TOKENS = ("lighthouse", "lighthouses", "office", "offices", "ocean")
# The original post and its "Community remix 2" clone carry the same facts; either detail page counts.
DETAIL_SLUGS = ("tiny-lighthouse-office-with-the-best-ocean-view-12",
                "community-remix-2-tiny-lighthouse-office-with-the-best-ocean-view-47")
ROOM_WIDTH = "4.2"
DESK_MATERIAL = ("reclaimed", "oak")
QUESTION = "Report the room's width and the material used for the desk."


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("seed_has_target_posts", all(post_by_slug(initial_db, s) for s in DETAIL_SLUGS), f"slugs={DETAIL_SLUGS!r}")
    answer = final_answer(traj)
    check_search_visited(judge, traj, SEARCH_TOKENS)
    check_detail_visited(judge, traj, DETAIL_SLUGS)
    judge.check("answer_has_room_width_meters", contains_decimal(answer, ROOM_WIDTH), f"expected={ROOM_WIDTH!r}, answer={answer!r}")
    judge.check("answer_has_desk_material", contains_all(answer, DESK_MATERIAL), f"expected={DESK_MATERIAL!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, "4.2 meters wide; desk built from reclaimed oak", QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
