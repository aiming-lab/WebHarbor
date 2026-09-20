#!/usr/bin/env python3
"""Verify AdoptAPet--1: cats near Scottsdale, AZ -> the kitten listed IN Scottsdale (Neo):
name, exact age in months, color, good with children (read-only).

The Scottsdale, AZ results contain two kittens (Neo in Scottsdale, Amba in Arizona City);
the task text pins the one whose listing is in Scottsdale itself.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    CHILDREN_KW, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pet, contains_all, contains_months, final_answer, run_verifier, stated_yes_no,
)

TASK_ID = "AdoptAPet--1"
PET = GT.pet("neo")  # Neo, 7 months, Black, good with children = Yes


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_cat_search_near_scottsdale",
                         location_any=({"scottsdale"},), species="Cat")
    check_visited_pet(judge, traj, PET["slug"])
    judge.check("answer_names_pet", contains_all(answer, [PET["name"]]), f"expected={PET['name']!r}, answer={answer!r}")
    judge.check("answer_has_age_months", contains_months(answer, PET["age_months"]),
                f"expected={PET['age_months']} months, answer={answer!r}")
    judge.check("answer_has_color", contains_all(answer, [PET["color"]]), f"expected={PET['color']!r}, answer={answer!r}")
    judge.check("answer_states_good_with_children_yes",
                stated_yes_no(answer, CHILDREN_KW, expected_yes=bool(PET["good_children"]), anchor_name=PET["name"]),
                f"expected=good with children: {'Yes' if PET['good_children'] else 'No'}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
