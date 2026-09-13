#!/usr/bin/env python3
"""Deterministic verifier for 4shared--6 (stateful: download).

Find The Federalist Papers in Books, verify 85 essays + searchable topic index on
its detail page, then use the Download button.

Checks: identity | searched/browsed Books | opened the detail page | the POST result
page /download/81 was reached after the detail page | DB: exactly one new downloads
row for file 81 (signed-in or anonymous), download_count +1 on that file only, every
other table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, check_detail_visited, check_download_recorded,  # noqa: E402
                        check_paths_in_order, check_search_or_category, check_tables_unchanged,
                        check_trajectory_identity, check_visited_path, fail_closed, load_run,
                        parse_args, resolve_snapshots, rows_unchanged_except)

TASK_ID = "4shared--6"
FILE_ID = 81
SLUG = "the-federalist-papers-epub-81"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search_or_category(j, t, "searched_federalist", any_tokens=["federalist"], categories=["books"])
    check_detail_visited(j, t, SLUG)
    check_visited_path(j, t, "reached_download_page", f"/download/{FILE_ID}")
    check_paths_in_order(j, t, "detail_before_download", [f"/file/{SLUG}", f"/download/{FILE_ID}"])
    check_download_recorded(j, initial_db, after_db, FILE_ID, user_id=None, allow_anonymous=True)
    j.check("other_files_unchanged", rows_unchanged_except(initial_db, after_db, "files", [FILE_ID]), f"files rows other than {FILE_ID} identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x not in {"downloads", "files"}])


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
