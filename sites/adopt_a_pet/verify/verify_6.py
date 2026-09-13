#!/usr/bin/env python3
"""Verify AdoptAPet--6: log in as alice.j, favorite Sirius, confirm Sirius + Luna under
Favorite pets (stateful: favorite +1 row exactly, login -> /pet/sirius -> /account order).
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

TASK_ID = "AdoptAPet--6"
EMAIL = "alice.j@test.com"
ADDED = GT.pet("sirius")
EXISTING = GT.pet("luna")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_signed_in_as(judge, traj, EMAIL)
    check_paths_in_order(judge, traj, "login_then_pet_then_account",
                         [("/login", {}), (f"/pet/{ADDED['slug']}", {}), ("/account", {})])
    check_exact_favorite_delta(judge, initial_db, after_db, added=[(EMAIL, ADDED["slug"])], removed=[])
    judge.check("account_lists_both_pets", favorite_slugs(after_db, EMAIL) == {ADDED["slug"], EXISTING["slug"]},
                f"after_favorites={sorted(favorite_slugs(after_db, EMAIL))!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "application", "pet_alert"))
    judge.check("answer_confirms_both_pets", contains_all(answer, [ADDED["name"], EXISTING["name"]]), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
