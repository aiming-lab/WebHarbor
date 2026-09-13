#!/usr/bin/env python3
"""Deterministic verifier for 4shared--9 (stateful: profile edit).

Log in as alice; set location to "Portland, Oregon" and bio to
"Community archive volunteer and urban sketcher."

Checks: identity | signed in as alice | opened /account/edit | DB: alice's users row
changed ONLY in location + bio to exactly those values (display name untouched);
other users and every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run,
                        normalize_text, parse_args, resolve_snapshots, row_by_id, row_changed_only_in,
                        rows_unchanged_except)

TASK_ID = "4shared--9"
EMAIL, USER_ID = "alice.j@test.com", 1
LOCATION = "Portland, Oregon"
BIO = "Community archive volunteer and urban sketcher."


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_account_settings", "/account/edit")
    ok, diff = row_changed_only_in(initial_db, after_db, "users", USER_ID, ("location", "bio"))
    after = row_by_id(after_db, "users", USER_ID) or {}
    j.check("alice_location_updated", normalize_text(after.get("location")) == normalize_text(LOCATION), f"after_location={after.get('location')!r}")
    j.check("alice_bio_updated", normalize_text(after.get("bio")) == normalize_text(BIO), f"after_bio={after.get('bio')!r}")
    j.check("alice_row_changed_only_location_bio", ok and bool(diff), f"diff={diff!r}")
    j.check("other_users_unchanged", rows_unchanged_except(initial_db, after_db, "users", [USER_ID]), "users rows other than alice identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "users"])


def main():
    a = parse_args()
    try:
        t = load_run(a.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(a, TASK_ID)
    j = Judge(TASK_ID, a.no_llm)
    try:
        run_checks(j, t, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
