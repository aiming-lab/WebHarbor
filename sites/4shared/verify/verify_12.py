#!/usr/bin/env python3
"""Deterministic verifier for 4shared--12 (stateful: rename + move).

Log in as alice; rename "Alice Quarterly retreat budget.xlsx" (file 123, in Work) to
"2027 Retreat Budget.xlsx" and move it into Shared Projects (folder 3).

Checks: identity | signed in as alice | opened /my-files | DB: file 123 changed ONLY
in filename/extension/folder_id/modified_at with the new name and folder 3; other
files rows and every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run, parse_args,
                        resolve_snapshots, row_by_id, row_changed_only_in, rows_unchanged_except)

TASK_ID = "4shared--12"
EMAIL, USER_ID = "alice.j@test.com", 1
FILE_ID = 123
NEW_NAME = "2027 Retreat Budget.xlsx"
DEST_FOLDER_ID = 3  # alice's "Shared Projects"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_my_files", "/my-files")
    ok, diff = row_changed_only_in(initial_db, after_db, "files", FILE_ID, ("filename", "extension", "folder_id", "modified_at"))
    after = row_by_id(after_db, "files", FILE_ID) or {}
    j.check("file_renamed", str(after.get("filename", "")).strip() == NEW_NAME and after.get("extension") == "xlsx", f"after_filename={after.get('filename')!r}")
    j.check("file_moved_to_shared_projects", after.get("folder_id") == DEST_FOLDER_ID, f"after_folder_id={after.get('folder_id')} expected={DEST_FOLDER_ID}")
    j.check("file_row_changed_only_expected_columns", ok and bool(diff), f"diff={diff!r}")
    j.check("other_files_unchanged", rows_unchanged_except(initial_db, after_db, "files", [FILE_ID]), f"files rows other than {FILE_ID} identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "files"])


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
