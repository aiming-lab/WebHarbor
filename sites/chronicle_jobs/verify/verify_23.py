#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--23 (stateful (bob alert delete)).

Log in as bob.c@test.com, delete only the location-restricted job alert and
report what the remaining alert searches for. DB: job_alerts row 4 (data /
Chicago, Illinois) removed, nothing else.
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

TASK_ID = "Chronicle Jobs--23"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "bob.c@test.com")
    check_account_section(j, t, "JobAlerts")
    check_only_rows_removed(j, initial_db, after_db, "job_alerts", [4], label="alert_delete")
    fa = final_answer(t)
    j.check("answer_has_remaining_keyword", contains_all(fa, ["librarian"]),
            f"expected remaining alert keyword='librarian' answer={fa[:200]!r}")


def main():
    from composed_grade import grade
    grade(23)


if __name__ == "__main__":
    main()
