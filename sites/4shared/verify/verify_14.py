#!/usr/bin/env python3
"""Deterministic verifier for 4shared--14 (stateful: share link).

Log in as alice; open "Alice Field recording notes.docx" (file 125) and create a share
link labeled "Audio volunteers" with Preview and download permission.

Checks: identity | signed in as alice | opened /file/125/share | DB: shared_links
gained exactly one row (alice, file 125, permission "download", label
"Audio volunteers"); every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run,
                        normalize_text, parse_args, resolve_snapshots, table_delta)

TASK_ID = "4shared--14"
EMAIL, USER_ID = "alice.j@test.com", 1
FILE_ID = 125
LABEL = "Audio volunteers"
PERMISSION = "download"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_share_page", f"/file/{FILE_ID}/share")
    delta = table_delta(initial_db, after_db, "shared_links")
    added = added_rows(initial_db, after_db, "shared_links")
    j.check("shared_links_exact_delta", len(added) == 1 and not delta["removed"] and not delta["changed"],
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    r = added[0] if added else {}
    j.check("link_is_alice_file_125", bool(r) and int(r["user_id"]) == USER_ID and int(r["file_id"]) == FILE_ID,
            f"user={r.get('user_id')} file={r.get('file_id')}")
    j.check("link_permission_download", bool(r) and r["permission"] == PERMISSION, f"permission={r.get('permission')!r}")
    j.check("link_label", bool(r) and normalize_text(r["label"]) == normalize_text(LABEL), f"label={r.get('label')!r}")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "shared_links"])


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
