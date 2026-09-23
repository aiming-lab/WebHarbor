#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--8 (read-only).

Browse the Chemistry discipline under Faculty Positions; report how many
chemistry jobs are listed and the institution hiring in Anchorage, Alaska.
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

TASK_ID = "Chronicle Jobs--8"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_browse(j, t, "browsed_chemistry", "chemistry")
    fa = final_answer(t)
    j.check("answer_has_count", contains_number(fa, 15), f"expected=15 answer={fa[:200]!r}")
    j.check("answer_has_institution", contains_all(fa, ["University of Alaska Anchorage"]),
            f"expected='University of Alaska Anchorage' answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    from composed_grade import grade
    grade(8)


if __name__ == "__main__":
    main()
