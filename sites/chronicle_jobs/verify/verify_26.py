#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--26 (stateful (david location)).

Log in as david.k@test.com, change the resume preferred location to
'Dallas, Texas', save, and report the location shown afterwards. DB: users
row 4 changed only in location.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_trajectory_identity, browse_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in_crlf, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--26"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "david.k@test.com")
    check_visited_path(j, t, "visited_resume_page", "/profilecv")
    check_row_edited_only_in_crlf(j, initial_db, after_db, "users", 4, ("location",), label="location_edit")
    after_row = rows_where(after_db, "users", "id = 4")[0]
    j.check("location_value_correct", "Dallas, Texas" == str(after_row["location"]),
            f"after={after_row['location']!r}")
    fa = final_answer(t)
    j.check("answer_has_location", contains_all(fa, ["Dallas", "Texas"]), f"answer={fa[:200]!r}")


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
