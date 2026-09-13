#!/usr/bin/env python3
"""Verify AdoptAPet--13: adult female dogs near Austin, TX -> Ruby: fee, good with cats (No),
good with children (No) (read-only).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    CATS_KW, CHILDREN_KW, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pet, contains_all, contains_money, final_answer, run_verifier, stated_yes_no,
)

TASK_ID = "AdoptAPet--13"
PET = GT.pet("ruby")  # $215, good with cats No, good with children No


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_female_dog_search_austin",
                         location_any=({"austin"}, {"tx"}, {"texas"}), species="Dog", sex="Female")
    check_visited_pet(judge, traj, PET["slug"])
    judge.check("answer_names_pet", contains_all(answer, [PET["name"]]), f"expected={PET['name']!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, PET["fee"]), f"expected=${PET['fee']}, answer={answer!r}")
    judge.check("answer_states_good_with_cats_no",
                stated_yes_no(answer, CATS_KW, expected_yes=bool(PET["good_cats"]), anchor_name=PET["name"]),
                f"expected=good with cats: {'Yes' if PET['good_cats'] else 'No'}, answer={answer!r}")
    judge.check("answer_states_good_with_children_no",
                stated_yes_no(answer, CHILDREN_KW, expected_yes=bool(PET["good_children"]), anchor_name=PET["name"]),
                f"expected=good with children: {'Yes' if PET['good_children'] else 'No'}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
