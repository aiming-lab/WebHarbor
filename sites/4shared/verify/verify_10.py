#!/usr/bin/env python3
"""Deterministic verifier for 4shared--10 (stateful: folder create).

Log in as bob; in My files create a root-level folder named "Survey Exports".

Checks: identity | signed in as bob | opened /my-files | DB: folders gained exactly
one row (bob, parent NULL, name "Survey Exports"); every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run, parse_args,
                        resolve_snapshots, table_delta)

TASK_ID = "4shared--10"
EMAIL, USER_ID = "bob.c@test.com", 2
FOLDER_NAME = "Survey Exports"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_my_files", "/my-files")
    delta = table_delta(initial_db, after_db, "folders")
    added = added_rows(initial_db, after_db, "folders")
    j.check("folders_exact_delta", len(added) == 1 and not delta["removed"] and not delta["changed"],
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    row = added[0] if added else {}
    j.check("new_folder_is_bobs_root_survey_exports",
            bool(row) and int(row["user_id"]) == USER_ID and row["parent_id"] is None and str(row["name"]).strip() == FOLDER_NAME,
            f"row={ {k: row.get(k) for k in ('user_id', 'parent_id', 'name')} if row else None!r}")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "folders"])


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
