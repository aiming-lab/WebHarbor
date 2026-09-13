#!/usr/bin/env python3
"""Deterministic verifier for 4shared--19 (search + favorite + download + report).

Log in as alice; broad search for archive metadata resources; the document with a
12-week sample schedule and a risk register on page 39 (file 96); add it to
Favorites, download it, report exact filename and total page count.

Checks: identity | signed in as alice | searched (archive/metadata) | opened the
target detail page | reached /download/96 | DB: favorites gained exactly (alice, 96);
exactly one new downloads row for file 96 by alice; download_count +1 on file 96
only; every other table row-identical | answer has exact filename + 46 pages.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_detail_visited, check_download_recorded,  # noqa: E402
                        check_search_or_category, check_signed_in_as, check_tables_unchanged,
                        check_trajectory_identity, check_visited_path, contains_filename, contains_number,
                        fail_closed, favorite_file_ids, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_unchanged_except, table_delta)

TASK_ID = "4shared--19"
EMAIL, USER_ID = "alice.j@test.com", 1
FILE_ID = 96
SLUG = "small-archive-digitization-plan-pdf-96"
FILENAME = "Small Archive Digitization Plan.pdf"
PAGES = 46


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_search_or_category(j, t, "searched_archive_metadata", any_tokens=["archive", "metadata", "digitization", "digitisation"], categories=["documents"])
    check_detail_visited(j, t, SLUG)
    check_visited_path(j, t, "reached_download_page", f"/download/{FILE_ID}")
    before, after = favorite_file_ids(initial_db, USER_ID), favorite_file_ids(after_db, USER_ID)
    j.check("initial_target_not_favorited", FILE_ID not in before, f"initial_favorites={sorted(before)!r}")
    delta = table_delta(initial_db, after_db, "favorites")
    added = added_rows(initial_db, after_db, "favorites")
    j.check("favorites_exact_delta",
            len(added) == 1 and not delta["removed"] and not delta["changed"]
            and int(added[0]["user_id"]) == USER_ID and int(added[0]["file_id"]) == FILE_ID,
            f"added={[(r['user_id'], r['file_id']) for r in added]!r} removed={len(delta['removed'])} changed={len(delta['changed'])} after={sorted(after)!r}")
    check_download_recorded(j, initial_db, after_db, FILE_ID, user_id=USER_ID, allow_anonymous=False)
    j.check("other_files_unchanged", rows_unchanged_except(initial_db, after_db, "files", [FILE_ID]), f"files rows other than {FILE_ID} identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x not in {"favorites", "downloads", "files"}])
    fa = final_answer(t)
    j.check("answer_has_exact_filename", contains_filename(fa, FILENAME), f"expected={FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_has_page_count", contains_number(fa, PAGES), f"expected={PAGES} answer={fa[:200]!r}")


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
