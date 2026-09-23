#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--18 (read-only (alice shortlist)).

Log in as alice.j@test.com and report the full titles of every saved job.
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

TASK_ID = "Chronicle Jobs--18"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "alice.j@test.com")
    check_account_section(j, t, "ShortList")
    fa = final_answer(t)
    j.check("answer_has_all_titles",
            contains_all(fa, ["Academic Program Director", "Part-Time Academic Coach",
                             "Research Associate", "Rockefeller Neuroscience Institute"]),
            f"expected all four saved titles answer={fa[:300]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    from composed_grade import grade
    grade(18)


if __name__ == "__main__":
    main()
