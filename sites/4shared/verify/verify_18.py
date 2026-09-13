#!/usr/bin/env python3
"""Deterministic verifier for 4shared--18 (comparison + stateful save).

Compare Pride and Prejudice (432 p / 61 ch), Anne of Green Gables (412 p / 38 ch) and
Twenty Thousand Leagues Under the Seas (512 p / 47 ch) by opening each detail page;
report the one with the most pages, its page count and chapter count; then log in
as david and save that book to My 4shared.

Checks: identity | all THREE detail pages opened | answer names Twenty Thousand
Leagues as the longest with 512 pages and 47 chapters | signed in as david | DB:
david had not saved file 90; saved_files gained exactly (david, 90); every other
table row-identical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, check_detail_visited, check_signed_in_as,  # noqa: E402
                        check_tables_unchanged, check_trajectory_identity, claims_winner,
                        contains_filename, contains_number, fail_closed, final_answer, load_run,
                        parse_args, resolve_snapshots, saved_file_ids, table_delta)

TASK_ID = "4shared--18"
EMAIL, USER_ID = "david.k@test.com", 4
SLUGS = ["pride-and-prejudice-epub-77", "anne-of-green-gables-epub-73", "twenty-thousand-leagues-under-the-seas-epub-90"]
WINNER_ID, WINNER_FILENAME, WINNER_KEY = 90, "Twenty Thousand Leagues Under the Seas.epub", "Twenty Thousand Leagues"
LOSER_KEYS = ["Pride and Prejudice", "Anne of Green Gables"]
PAGES, CHAPTERS = 512, 47


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    for slug in SLUGS:
        check_detail_visited(j, t, slug)
    fa = final_answer(t)
    j.check("answer_names_longest_book", contains_filename(fa, WINNER_FILENAME) or claims_winner(fa, WINNER_KEY, LOSER_KEYS, cue=r"most|longest|largest|more|highest|biggest"),
            f"expected={WINNER_FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_not_crediting_a_loser", claims_winner(fa, WINNER_KEY, LOSER_KEYS, cue=r"most|longest|largest|more|highest|biggest"), f"answer={fa[:200]!r}")
    j.check("answer_has_page_count", contains_number(fa, PAGES), f"expected={PAGES} answer={fa[:200]!r}")
    j.check("answer_has_chapter_count", contains_number(fa, CHAPTERS), f"expected={CHAPTERS} answer={fa[:200]!r}")
    check_signed_in_as(j, t, EMAIL)
    before, after = saved_file_ids(initial_db, USER_ID), saved_file_ids(after_db, USER_ID)
    j.check("initial_target_not_saved", WINNER_ID not in before, f"initial_saved={sorted(before)!r}")
    j.check("target_saved_for_david", WINNER_ID in after, f"after_saved={sorted(after)!r}")
    delta = table_delta(initial_db, after_db, "saved_files")
    added = added_rows(initial_db, after_db, "saved_files")
    j.check("saved_files_exact_delta",
            len(added) == 1 and not delta["removed"] and not delta["changed"]
            and int(added[0]["user_id"]) == USER_ID and int(added[0]["file_id"]) == WINNER_ID,
            f"added={[(r['user_id'], r['file_id']) for r in added]!r} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x != "saved_files"])


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
