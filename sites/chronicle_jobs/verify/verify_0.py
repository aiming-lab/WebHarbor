#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--0 (read-only).

Search 'librarian', report the total found, switch to 'Newest first' and
report the posted date of the newest librarian job. Checks: identity |
'librarian' keyword search | Date sort applied | newest job detail opened |
answer states the total and the posted date | read-only DB.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, site_urls, check_trajectory_identity, browse_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--0"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search(j, t, "searched_librarian", all_tokens=["librarian"])
    # the sort switch must appear in some recorded URL (sort=Date)
    ok_sort = any("sort=Date" in u for u in [u for u in __import__('verify_lib').site_urls(t)])
    j.check("switched_to_newest_first", ok_sort, "required: a URL with sort=Date")
    check_detail_visited(j, t, 38041825, "associate-university-librarian-aul-for-user-services-research-and-technology")
    fa = final_answer(t)
    j.check("answer_has_total", contains_number(fa, 33), f"expected=33 answer={fa[:200]!r}")
    j.check("answer_has_newest_posted_date", contains_month_date(fa, "Sep 21, 2026"),
            f"expected='Sep 21, 2026' answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


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
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
