#!/usr/bin/env python3
"""Deterministic verifier for 4shared--17 (stateful, multi-step).

Log in as carol; create root folder "Workshop Handouts"; upload a private 384 KB
spring-workshop-outline.pdf into it with the given description; rename it to
final-spring-workshop-outline.pdf; create a preview-only share link labeled
"Planning committee".

Checks: identity | signed in as carol | opened /my-files, /upload and the new file's
share page | DB: folders +1 (carol, root, "Workshop Handouts"); files +1 (carol, in
that folder, final name, 393216 bytes, exact description, private, Documents, and
modified_at >= uploaded_at i.e. renamed after upload); shared_links +1 (carol, that
file, permission "view", label "Planning committee") created after the rename; every
other table and pre-existing row identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_signed_in_as, check_tables_unchanged,  # noqa: E402
                        check_trajectory_identity, check_visited_path, fail_closed, load_run,
                        navigated_to_path, normalize_text, parse_args, resolve_snapshots,
                        rows_unchanged_except, table_delta)

TASK_ID = "4shared--17"
EMAIL, USER_ID = "carol.d@test.com", 3
FOLDER_NAME = "Workshop Handouts"
FINAL_NAME = "final-spring-workshop-outline.pdf"
SIZE_BYTES = 384 * 1024
DESCRIPTION = "Draft outline for the spring neighborhood workshop."
LABEL, PERMISSION = "Planning committee", "view"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_my_files", "/my-files")
    check_visited_path(j, t, "visited_upload_form", "/upload")
    for table in ("folders", "files", "shared_links"):
        d = table_delta(initial_db, after_db, table)
        j.check(f"{table}_exact_delta", len(d["added"]) == 1 and not d["removed"] and not d["changed"],
                f"table={table} added={len(d['added'])} removed={len(d['removed'])} changed={len(d['changed'])}")
    folder = (added_rows(initial_db, after_db, "folders") or [{}])[0]
    f = (added_rows(initial_db, after_db, "files") or [{}])[0]
    link = (added_rows(initial_db, after_db, "shared_links") or [{}])[0]
    j.check("new_folder_is_carols_root_workshop_handouts",
            bool(folder) and int(folder["user_id"]) == USER_ID and folder["parent_id"] is None and str(folder["name"]).strip() == FOLDER_NAME,
            f"folder={ {k: folder.get(k) for k in ('user_id', 'parent_id', 'name')} if folder else None!r}")
    j.check("new_file_in_new_folder_owned_by_carol",
            bool(f) and bool(folder) and int(f["owner_id"]) == USER_ID and f["folder_id"] == folder["id"],
            f"owner={f.get('owner_id')} folder_id={f.get('folder_id')} new_folder_id={folder.get('id')}")
    j.check("new_file_final_name", bool(f) and str(f["filename"]).strip() == FINAL_NAME and f["extension"] == "pdf", f"filename={f.get('filename')!r}")
    j.check("new_file_size_384kb", bool(f) and int(f["size_bytes"]) == SIZE_BYTES, f"size_bytes={f.get('size_bytes')} expected={SIZE_BYTES}")
    j.check("new_file_description", bool(f) and normalize_text(f["description"]) == normalize_text(DESCRIPTION), f"description={f.get('description')!r}")
    j.check("new_file_private_documents", bool(f) and not f["public"] and not f["deleted"] and f["category"] == "Documents",
            f"public={f.get('public')} deleted={f.get('deleted')} category={f.get('category')!r}")
    j.check("file_renamed_after_upload", bool(f) and str(f["modified_at"]) >= str(f["uploaded_at"]), f"uploaded_at={f.get('uploaded_at')} modified_at={f.get('modified_at')}")
    j.check("share_link_for_new_file_preview_only",
            bool(link) and bool(f) and int(link["user_id"]) == USER_ID and link["file_id"] == f["id"]
            and link["permission"] == PERMISSION and normalize_text(link["label"]) == normalize_text(LABEL),
            f"link={ {k: link.get(k) for k in ('user_id', 'file_id', 'permission', 'label')} if link else None!r}")
    j.check("share_link_created_after_rename", bool(link) and bool(f) and str(link["created_at"]) >= str(f["modified_at"]),
            f"file_modified_at={f.get('modified_at')} link_created_at={link.get('created_at')}")
    j.check("visited_new_file_share_page", bool(f) and navigated_to_path(t, f"/file/{f['id']}/share"), f"required_path=/file/{f.get('id')}/share")
    j.check("other_files_unchanged", rows_unchanged_except(initial_db, after_db, "files", [f["id"]] if f else []), "pre-existing files rows identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x not in {"folders", "files", "shared_links"}])


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
