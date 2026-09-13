#!/usr/bin/env python3
"""Verify AdoptAPet--4: find Arno through the pet search, then the rescue's name, phone and
e-mail from the pet profile + linked shelter page (read-only).

The profile names the rescue; phone and e-mail are only on /shelter/<id>.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, check_visited_path, check_visited_pet,
    contains_all, contains_email, contains_phone, final_answer, navigated_to_path, run_verifier,
)

TASK_ID = "AdoptAPet--4"
PET = GT.pet("arno")
SHELTER = GT.shelter(PET["shelter_id"])  # Desert Paws Rescue, 602-555-0141, hello@desertpaws.test


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("used_pet_search", navigated_to_path(traj, "/search"), "required_path=/search (any query)")
    check_visited_pet(judge, traj, PET["slug"])
    check_visited_path(judge, traj, f"visited_shelter_{SHELTER['id']}", f"/shelter/{SHELTER['id']}")
    judge.check("answer_has_rescue_name", contains_all(answer, [SHELTER["name"]]), f"expected={SHELTER['name']!r}, answer={answer!r}")
    judge.check("answer_has_rescue_phone", contains_phone(answer, SHELTER["phone"]), f"expected={SHELTER['phone']!r}, answer={answer!r}")
    judge.check("answer_has_rescue_email", contains_email(answer, SHELTER["email"]), f"expected={SHELTER['email']!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
