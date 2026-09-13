#!/usr/bin/env python3
"""Verify AdoptAPet--9: log in as carol.w, create a New Pet Alert (Cat / Siamese / 33130 /
50 miles), confirm it in the account (stateful: pet_alert +1 row with exact values).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_paths_in_order, check_signed_in_as, check_tables_unchanged, check_trajectory_identity,
    contains_all, contains_count, final_answer, normalize_text, run_verifier, table_delta, user_id_for_email,
)

TASK_ID = "AdoptAPet--9"
EMAIL = "carol.w@test.com"
SPECIES, BREED, POSTAL, RADIUS = "Cat", "Siamese", "33130", 50


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_signed_in_as(judge, traj, EMAIL)
    check_paths_in_order(judge, traj, "login_alerts_account", [("/login", {}), ("/alerts", {}), ("/account", {})])
    delta = table_delta(initial_db, after_db, "pet_alert")
    judge.check("exactly_one_alert_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"added={delta['added']!r}, removed={delta['removed']!r}, changed={delta['changed']!r}")
    row = delta["added"][0] if delta["added"] else {}
    uid = user_id_for_email(after_db, EMAIL)
    judge.check("alert_belongs_to_carol", row.get("user_id") == uid, f"expected user_id={uid}, row={row!r}")
    judge.check("alert_values_exact",
                normalize_text(row.get("species")) == normalize_text(SPECIES) and normalize_text(row.get("breed")) == normalize_text(BREED)
                and str(row.get("postal") or "").strip() == POSTAL and int(row.get("radius") or 0) == RADIUS,
                f"expected=({SPECIES}, {BREED}, {POSTAL}, {RADIUS}), row={row!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "favorite", "application"))
    judge.check("answer_confirms_alert", contains_all(answer, [BREED, POSTAL]) and contains_count(answer, RADIUS), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
