#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--27 (read-only (Delaware hub)).

Open the University of Delaware employer hub via the employers directory;
report how many job openings it lists and the title of one of its newest jobs.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_trajectory_identity, browse_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--27"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_visited_path(j, t, "visited_employers_directory", "/employers")
    check_employer_hub(j, t, "university-of-delaware")
    fa = final_answer(t)
    j.check("answer_has_opening_count", contains_number(fa, 40), f"expected=40 answer={fa[:200]!r}")
    latest = ['Digital Accessibility Manager', 'Auxiliary Security Officer, UDPD', 'Manager, Student Basic Needs', 'Multimedia Specialist, Athletics', 'Applications Programmer III, Office of Educational Technology', 'Academic Advisor II, Lerner College Business & Economics']
    
    j.check("answer_names_newest_job", contains_any(fa, latest), f"expected one of latest titles answer={fa[:200]!r}")
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
