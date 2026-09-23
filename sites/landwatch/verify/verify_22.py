#!/usr/bin/env python3
"""Verify LandWatch--22 — '3D Mountain Ranch' detail facts.

Ground truth (frozen seed): $6,995,000, 11,764 Acres, Type row 'Farms and
Ranches, Recreational Property, Hunting Property'.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--22"
DETAIL_PATH = "/moffat-county-colorado-farms-and-ranches-for-sale/pid/424462143"
TYPES = ["Farms and Ranches", "Recreational Property", "Hunting Property"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_3d_mountain_ranch", DETAIL_PATH)
    judge.check("answer_price", contains_money(answer, 6995000),
                "expected $6,995,000")
    judge.check("answer_acres", contains_acres(answer, 11764),
                "expected 11,764 Acres")
    for t in TYPES:
        judge.check(f"answer_type_{t.lower().replace(' ', '_')}", contains_phrase(answer, t),
                    f"expected the Type row to include {t!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
