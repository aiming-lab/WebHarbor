#!/usr/bin/env python3
"""Deterministic verifier for 4shared--11 (stateful: upload record).

Log in as carol; upload a private file record accessibility-session-notes.pdf,
640 KB, with the given description, into the Work folder.

Checks: identity | signed in as carol | opened /upload | DB: files gained exactly one
row owned by carol in her Work folder (id 9) with that filename, 655360 bytes, the
exact description, private, category Documents; other files rows and every other
table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run,
                        normalize_text, parse_args, resolve_snapshots, rows_unchanged_except, table_delta)

TASK_ID = "4shared--11"
EMAIL, USER_ID = "carol.d@test.com", 3
WORK_FOLDER_ID = 9
FILENAME = "accessibility-session-notes.pdf"
SIZE_BYTES = 640 * 1024
DESCRIPTION = "Notes and action items from the accessibility session."


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_upload_form", "/upload")
    delta = table_delta(initial_db, after_db, "files")
    added = added_rows(initial_db, after_db, "files")
    j.check("files_exact_delta", len(added) == 1 and not delta["removed"] and not delta["changed"],
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    r = added[0] if added else {}
    j.check("upload_owner_and_folder", bool(r) and int(r["owner_id"]) == USER_ID and r["folder_id"] == WORK_FOLDER_ID,
            f"owner={r.get('owner_id')} folder={r.get('folder_id')} expected_folder={WORK_FOLDER_ID}")
    j.check("upload_filename", bool(r) and str(r["filename"]).strip() == FILENAME, f"filename={r.get('filename')!r}")
    j.check("upload_size_640kb", bool(r) and int(r["size_bytes"]) == SIZE_BYTES, f"size_bytes={r.get('size_bytes')} expected={SIZE_BYTES}")
    j.check("upload_description", bool(r) and normalize_text(r["description"]) == normalize_text(DESCRIPTION), f"description={r.get('description')!r}")
    j.check("upload_private_documents", bool(r) and not r["public"] and not r["deleted"] and r["category"] == "Documents",
            f"public={r.get('public')} deleted={r.get('deleted')} category={r.get('category')!r}")
    j.check("other_files_unchanged", rows_unchanged_except(initial_db, after_db, "files", [r["id"]] if r else []), "pre-existing files rows identical")
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
