#!/usr/bin/env python3
"""Verify AdoptAPet--14: pets near New York, NY -> Luna ($250) vs Milo ($150), lower = Milo (read-only)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    HIGHEST, LOWEST, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pets, contains_all, contains_money, final_answer, identifies, run_verifier,
)

TASK_ID = "AdoptAPet--14"
LUNA, MILO = GT.pet("luna"), GT.pet("milo")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_search_near_new_york", location_any=({"new", "york"}, {"ny"}))
    check_visited_pets(judge, traj, [LUNA["slug"], MILO["slug"]])
    judge.check("answer_names_both_pets", contains_all(answer, [LUNA["name"], MILO["name"]]), f"answer={answer!r}")
    judge.check("answer_has_both_fees", contains_money(answer, LUNA["fee"]) and contains_money(answer, MILO["fee"]),
                f"expected=${LUNA['fee']} and ${MILO['fee']}, answer={answer!r}")
    judge.check("answer_identifies_lower_fee_pet", identifies(answer, MILO["name"], [LUNA["name"]], LOWEST, HIGHEST),
                f"winner={MILO['name']!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
