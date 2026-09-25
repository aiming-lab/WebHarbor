#!/usr/bin/env python3
"""Verify AdoptAPet--7: log in as alice.j, remove Luna from favorites, confirm she is gone
(stateful: favorite -1 row exactly; the only remove control is on /pet/luna).
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

TASK_ID = "AdoptAPet--7"
EMAIL = "alice.j@test.com"
REMOVED = GT.pet("luna")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_signed_in_as(judge, traj, EMAIL)
    check_paths_in_order(judge, traj, "login_then_pet_then_account",
                         [("/login", {}), (f"/pet/{REMOVED['slug']}", {}), ("/account", {})])
    check_exact_favorite_delta(judge, initial_db, after_db, added=[], removed=[(EMAIL, REMOVED["slug"])])
    judge.check("account_has_no_favorites_left", favorite_slugs(after_db, EMAIL) == set(),
                f"after_favorites={sorted(favorite_slugs(after_db, EMAIL))!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "application", "pet_alert"))
    judge.check("answer_mentions_pet", contains_all(answer, [REMOVED["name"]]), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
