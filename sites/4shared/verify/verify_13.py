#!/usr/bin/env python3
"""Deterministic verifier for 4shared--13 (stateful: restore from Trash).

Log in as david; open Trash and restore "David Old outline.txt" (file 146).

Checks: identity | signed in as david | opened /trash | DB: file 146 changed ONLY in
deleted (1 -> 0) and modified_at; other files rows and every other table
row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run, parse_args,
                        resolve_snapshots, row_by_id, row_changed_only_in, rows_unchanged_except)

TASK_ID = "4shared--13"
EMAIL, USER_ID = "david.k@test.com", 4
FILE_ID = 146


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_trash", "/trash")
    before, after = row_by_id(initial_db, "files", FILE_ID) or {}, row_by_id(after_db, "files", FILE_ID) or {}
    j.check("initial_file_in_trash", bool(before) and bool(before.get("deleted")), f"initial_deleted={before.get('deleted')!r}")
    j.check("file_restored", bool(after) and not after.get("deleted"), f"after_deleted={after.get('deleted')!r}")
    ok, diff = row_changed_only_in(initial_db, after_db, "files", FILE_ID, ("deleted", "modified_at"))
    j.check("file_row_changed_only_deleted_flag", ok and "deleted" in diff, f"diff={diff!r}")
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
