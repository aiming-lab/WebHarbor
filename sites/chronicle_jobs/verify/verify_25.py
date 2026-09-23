#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--25 (stateful (alice headline)).

Log in as alice.j@test.com, edit the resume professional headline to
'Aspiring dean of academic affairs', save, and report the headline shown
afterwards. DB: users row 1 changed only in headline.
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

TASK_ID = "Chronicle Jobs--25"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "alice.j@test.com")
    check_visited_path(j, t, "visited_resume_page", "/profilecv")
    check_row_edited_only_in_crlf(j, initial_db, after_db, "users", 1, ("headline",), label="headline_edit")
    after_row = rows_where(after_db, "users", "id = 1")[0]
    j.check("headline_value_correct", "Aspiring dean of academic affairs" == str(after_row["headline"]),
            f"after={after_row['headline']!r}")
    fa = final_answer(t)
    j.check("answer_has_headline", contains_all(fa, ["Aspiring dean of academic affairs"]),
            f"expected='Aspiring dean of academic affairs' answer={fa[:200]!r}")


def main():
    from composed_grade import grade
    grade(25)


if __name__ == "__main__":
    main()
