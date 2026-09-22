#!/usr/bin/env python3
"""Verify 9GAG--16: Alice logs in and updates display name, bio and location in Settings (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_only_tables_changed, check_paths_in_order, check_signed_in_as, check_trajectory_identity,
    check_visited_path, normalize_text, run_verifier, table_delta, user_id_for_email, user_row,
)

TASK_ID = "9GAG--16"
EMAIL, USERNAME = "alice.j@test.com", "alice_j"
DISPLAY_NAME = "Alice J."
BIO = "Memes, trail photos, and excellent tiny libraries."
LOCATION = "Tacoma, WA"
FROZEN_COLUMNS = ("id", "username", "email", "password_hash", "joined_at")


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    user_id = user_id_for_email(initial_db, EMAIL)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_settings_page", "/settings")
    check_paths_in_order(judge, traj, "workflow_login_before_settings", [("/login", {}), ("/settings", {})])
    before, after = user_row(initial_db, EMAIL) or {}, user_row(after_db, EMAIL) or {}
    judge.check("initial_profile_requires_update",
                normalize_text(before.get("display_name")) != normalize_text(DISPLAY_NAME)
                or normalize_text(before.get("location")) != normalize_text(LOCATION),
                f"initial display_name={before.get('display_name')!r}, location={before.get('location')!r}")
    judge.check("profile_fields_updated",
                normalize_text(after.get("display_name")) == normalize_text(DISPLAY_NAME)
                and normalize_text(after.get("bio")) == normalize_text(BIO)
                and normalize_text(after.get("location")) == normalize_text(LOCATION),
                f"expected display_name={DISPLAY_NAME!r}, bio={BIO!r}, location={LOCATION!r}; "
                f"after display_name={after.get('display_name')!r}, bio={after.get('bio')!r}, location={after.get('location')!r}")
    delta = table_delta(initial_db, after_db, "user")
    exact = (not delta["added"] and not delta["removed"] and len(delta["changed"]) == 1
             and int(delta["changed"][0][0][0]) == user_id
             and all(before.get(c) == after.get(c) for c in FROZEN_COLUMNS))
    judge.check("user_exact_delta", exact, f"expected only user {user_id}'s profile columns to change; delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("user",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
