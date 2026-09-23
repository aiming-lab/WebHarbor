#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--1 (read-only).

Search 'Klarman', open the postdoctoral fellowship posting, report the annual
stipend, the per-year research-expense allowance, and the appointment-start window.
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

TASK_ID = "Chronicle Jobs--1"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search(j, t, "searched_klarman", all_tokens=["Klarman"])
    check_detail_visited(j, t, 38022848, "klarman-postdoctoral-fellowships-college-of-arts-and-sciences-cornell-university")
    from verify_lib import money_claim
    fa = final_answer(t)
    j.check("answer_has_stipend", money_claim(fa, r"stipend", 80000), f"expected=$80,000 answer={fa[:200]!r}")
    j.check("answer_has_allowance", money_claim(fa, r"research(?:[- ]expense)?(?: allowance| expenses)?", 12000), f"expected=$12,000 answer={fa[:200]!r}")
    j.check("answer_has_window", contains_all(fa, ["July", "September", "2027"]),
            f"expected window July..September 2027 answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    from composed_grade import grade
    grade(1)


if __name__ == "__main__":
    main()
