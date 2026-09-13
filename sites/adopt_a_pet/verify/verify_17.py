#!/usr/bin/env python3
"""Verify AdoptAPet--17: senior dogs near Miami, FL -> Teddy: 96 months, Poodle / Mixed Breed,
$185, house-trained Yes (read-only).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    HOUSE_TRAINED_KW, Judge, check_read_only, check_search_visited, check_trajectory_identity, check_visited_pet,
    contains_all, contains_money, contains_months, final_answer, run_verifier, stated_yes_no,
)

TASK_ID = "AdoptAPet--17"
PET = GT.pet("teddy")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_senior_dog_search_miami",
                         location_any=({"miami"}, {"fl"}, {"florida"}), species="Dog", age="Senior")
    check_visited_pet(judge, traj, PET["slug"])
    judge.check("answer_names_pet", contains_all(answer, [PET["name"]]), f"expected={PET['name']!r}, answer={answer!r}")
    judge.check("answer_has_age_months", contains_months(answer, PET["age_months"]), f"expected={PET['age_months']} months, answer={answer!r}")
    judge.check("answer_has_both_breeds", contains_all(answer, GT.breeds(PET)), f"expected={GT.breeds(PET)!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, PET["fee"]), f"expected=${PET['fee']}, answer={answer!r}")
    judge.check("answer_states_house_trained_yes",
                stated_yes_no(answer, HOUSE_TRAINED_KW, expected_yes=bool(PET["house_trained"]), anchor_name=PET["name"]),
                f"expected=house-trained: {'Yes' if PET['house_trained'] else 'No'}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
