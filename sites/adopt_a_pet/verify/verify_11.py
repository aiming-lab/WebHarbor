#!/usr/bin/env python3
"""Verify AdoptAPet--11: Breed 101 -> Maine Coon -> Milo: name, sex, location, fee (read-only).
The fee is only on the profile page.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_search_visited, check_trajectory_identity, check_visited_path, check_visited_pet,
    contains_all, contains_money, final_answer, run_verifier,
)

TASK_ID = "AdoptAPet--11"
PET = GT.pet("milo")  # Male, New York, NY, $150


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_visited_path(judge, traj, "visited_breed_101", "/breeds")
    check_search_visited(judge, traj, "visited_maine_coon_results", breed="Maine Coon", species="Cat")
    check_visited_pet(judge, traj, PET["slug"])
    judge.check("answer_names_pet", contains_all(answer, [PET["name"]]), f"expected={PET['name']!r}, answer={answer!r}")
    judge.check("answer_has_sex", contains_all(answer, [PET["sex"]]), f"expected={PET['sex']!r}, answer={answer!r}")
    judge.check("answer_has_location", contains_all(answer, [PET["city"]]), f"expected={PET['city']!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, PET["fee"]), f"expected=${PET['fee']}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
