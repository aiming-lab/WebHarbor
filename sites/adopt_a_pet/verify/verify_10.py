#!/usr/bin/env python3
"""Verify AdoptAPet--10: Find a shelter -> Seattle -> Pacific Animal Haven: name, phone,
e-mail and every pet shown (Daisy, Pepper) (read-only).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, check_visited_path, contains_all, contains_email,
    contains_phone, final_answer, run_verifier, shelters_search_visited,
)

TASK_ID = "AdoptAPet--10"
SHELTER = GT.shelter(4)  # Pacific Animal Haven
PETS = [p for p in GT.PETS if p["shelter_id"] == SHELTER["id"]]  # Daisy, Pepper


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("used_shelter_search_for_seattle", shelters_search_visited(traj, ({"seattle"}, {"wa"}, {"pacific"})),
                "required=/shelters?q~seattle")
    check_visited_path(judge, traj, f"visited_shelter_{SHELTER['id']}", f"/shelter/{SHELTER['id']}")
    judge.check("answer_has_shelter_name", contains_all(answer, [SHELTER["name"]]), f"expected={SHELTER['name']!r}, answer={answer!r}")
    judge.check("answer_has_phone", contains_phone(answer, SHELTER["phone"]), f"expected={SHELTER['phone']!r}, answer={answer!r}")
    judge.check("answer_has_email", contains_email(answer, SHELTER["email"]), f"expected={SHELTER['email']!r}, answer={answer!r}")
    judge.check("answer_lists_every_pet", contains_all(answer, [p["name"] for p in PETS]),
                f"expected={[p['name'] for p in PETS]!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
