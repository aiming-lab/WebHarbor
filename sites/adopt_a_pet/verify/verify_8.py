#!/usr/bin/env python3
"""Verify AdoptAPet--8: log in as bob.smith, submit an adoption inquiry for Daisy with the
given phone / housing / experience, confirm it is Submitted in the account
(stateful: application +1 row with exact field values).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    Judge, check_paths_in_order, check_signed_in_as, check_tables_unchanged, check_trajectory_identity,
    contains_all, digits_only, final_answer, normalize_text, run_verifier, table_delta, user_id_for_email,
)

TASK_ID = "AdoptAPet--8"
EMAIL = "bob.smith@test.com"
PET = GT.pet("daisy")
PHONE = "206-555-0199"
HOUSING = "Rent with permission"
EXPERIENCE = "I have cared for two family dogs for eight years."


def _squash(text: object) -> str:
    return normalize_text(text).rstrip(" .!")


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_signed_in_as(judge, traj, EMAIL)
    check_paths_in_order(judge, traj, "login_pet_apply_account",
                         [("/login", {}), (f"/pet/{PET['slug']}", {}), (f"/apply/{PET['slug']}", {}), ("/account", {})])
    delta = table_delta(initial_db, after_db, "application")
    judge.check("exactly_one_application_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"added={delta['added']!r}, removed={delta['removed']!r}, changed={delta['changed']!r}")
    row = delta["added"][0] if delta["added"] else {}
    uid = user_id_for_email(after_db, EMAIL)
    judge.check("application_belongs_to_bob_for_daisy", row.get("user_id") == uid and row.get("pet_id") == PET["id"],
                f"expected user_id={uid} pet_id={PET['id']}, row={row!r}")
    judge.check("application_housing_exact", normalize_text(row.get("housing")) == normalize_text(HOUSING),
                f"expected={HOUSING!r}, observed={row.get('housing')!r}")
    judge.check("application_phone_exact", digits_only(row.get("phone")) == digits_only(PHONE),
                f"expected={PHONE!r}, observed={row.get('phone')!r}")
    judge.check("application_experience_exact", _squash(row.get("experience")) == _squash(EXPERIENCE),
                f"expected={EXPERIENCE!r}, observed={row.get('experience')!r}")
    judge.check("application_status_submitted", normalize_text(row.get("status")) == "submitted",
                f"observed_status={row.get('status')!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "favorite", "pet_alert"))
    judge.check("answer_confirms_submitted_for_daisy", contains_all(answer, [PET["name"], "Submitted"]), f"answer={answer!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
