#!/usr/bin/env python3
"""Deterministic verifier for 4shared--15 (stateful: comment).

Log in as bob; find Beginner Map Reading Workbook (file 93) and post the comment
"The coordinate exercises are ideal for our Saturday workshop."

Checks: identity | signed in as bob | opened the target detail page | DB: comments
gained exactly one row (bob, file 93, exact body); every other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_detail_visited, check_signed_in_as,  # noqa: E402
                        check_tables_unchanged, check_trajectory_identity, fail_closed, load_run,
                        normalize_text, parse_args, resolve_snapshots, table_delta)

TASK_ID = "4shared--15"
EMAIL, USER_ID = "bob.c@test.com", 2
FILE_ID = 93
SLUG = "beginner-map-reading-workbook-pdf-93"
BODY = "The coordinate exercises are ideal for our Saturday workshop."


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_detail_visited(j, t, SLUG)
    delta = table_delta(initial_db, after_db, "comments")
    added = added_rows(initial_db, after_db, "comments")
    j.check("comments_exact_delta", len(added) == 1 and not delta["removed"] and not delta["changed"],
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    r = added[0] if added else {}
    j.check("comment_is_bob_on_file_93", bool(r) and int(r["user_id"]) == USER_ID and int(r["file_id"]) == FILE_ID,
            f"user={r.get('user_id')} file={r.get('file_id')}")
    j.check("comment_body_exact", bool(r) and normalize_text(r["body"]) == normalize_text(BODY), f"body={r.get('body')!r}")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "comments"])


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
