#!/usr/bin/env python3
"""Deterministic verifier for 4shared--7 (stateful: favorite).

Log in as alice, find ArchivePeek File Inspector, add it to Favorites, open
Favorites to confirm.

Checks: identity | signed in as alice | opened the target detail page | opened
/favorites after it | DB: alice did not already favorite file 38; favorites gained
exactly one row (alice, 38); every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_detail_visited, check_paths_in_order,  # noqa: E402
                        check_signed_in_as, check_tables_unchanged, check_trajectory_identity,
                        check_visited_path, fail_closed, favorite_file_ids, load_run, parse_args,
                        resolve_snapshots, table_delta)

TASK_ID = "4shared--7"
EMAIL, USER_ID = "alice.j@test.com", 1
FILE_ID = 38
SLUG = "archivepeek-file-inspector-zip-38"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_detail_visited(j, t, SLUG)
    check_visited_path(j, t, "visited_favorites_page", "/favorites")
    check_paths_in_order(j, t, "workflow_in_order", ["/login", f"/file/{SLUG}", "/favorites"])
    before, after = favorite_file_ids(initial_db, USER_ID), favorite_file_ids(after_db, USER_ID)
    j.check("initial_target_not_favorited", FILE_ID not in before, f"initial_favorites={sorted(before)!r}")
    j.check("target_favorited_for_alice", FILE_ID in after, f"after_favorites={sorted(after)!r}")
    delta = table_delta(initial_db, after_db, "favorites")
    added = added_rows(initial_db, after_db, "favorites")
    j.check("favorites_exact_delta",
            len(added) == 1 and not delta["removed"] and not delta["changed"]
            and int(added[0]["user_id"]) == USER_ID and int(added[0]["file_id"]) == FILE_ID,
            f"added={[(r['user_id'], r['file_id']) for r in added]!r} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "favorites"])


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
