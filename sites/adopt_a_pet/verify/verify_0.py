#!/usr/bin/env python3
"""Verify AdoptAPet--0: dogs near Phoenix, AZ -> Waymo's breed, age group, size and fee (read-only).

Deterministic only. Ground truth is frozen in ground_truth.py (re-validated against the
initial snapshot); nothing here reads tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_search_visited, check_trajectory_identity, check_visited_pet,
    contains_all, contains_money, final_answer, run_verifier,
)

TASK_ID = "AdoptAPet--0"
PET = GT.pet("waymo")  # American Pit Bull Terrier / Mixed Breed, Adult, Large, $225


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_dog_search_near_phoenix",
                         location_any=({"phoenix"}, {"85004"}), species="Dog")
    check_visited_pet(judge, traj, PET["slug"])
    judge.check("answer_has_both_breeds", contains_all(answer, GT.breeds(PET)),
                f"expected={GT.breeds(PET)!r}, answer={answer!r}")
    judge.check("answer_has_age_group", contains_all(answer, [PET["age_group"]]),
                f"expected={PET['age_group']!r}, answer={answer!r}")
    judge.check("answer_has_size", contains_all(answer, [PET["size"]]),
                f"expected={PET['size']!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, PET["fee"]),
                f"expected=${PET['fee']}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
