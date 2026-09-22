#!/usr/bin/env python3
"""Verify AdoptAPet--15: log in as david.b, favorite Archie and Ruby, confirm both in Favorite
pets (stateful: favorite +2 rows exactly, account visited after both profiles).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_exact_favorite_delta, check_paths_in_order, check_signed_in_as, check_tables_unchanged,
    check_trajectory_identity, contains_all, favorite_slugs, final_answer, run_verifier,
)

TASK_ID = "AdoptAPet--15"
EMAIL = "david.b@test.com"
PETS = [GT.pet("archie"), GT.pet("ruby")]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_signed_in_as(judge, traj, EMAIL)
    for pet in PETS:
        check_paths_in_order(judge, traj, f"login_then_{pet['slug']}_then_account",
                             [("/login", {}), (f"/pet/{pet['slug']}", {}), ("/account", {})])
    check_exact_favorite_delta(judge, initial_db, after_db, added=[(EMAIL, p["slug"]) for p in PETS], removed=[])
    judge.check("account_lists_both_pets", favorite_slugs(after_db, EMAIL) == {p["slug"] for p in PETS},
                f"after_favorites={sorted(favorite_slugs(after_db, EMAIL))!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "application", "pet_alert"))
    judge.check("answer_confirms_both_pets", contains_all(answer, [p["name"] for p in PETS]), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
