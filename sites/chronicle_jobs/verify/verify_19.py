#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--19 (stateful (carol withdraw)).

Log in as carol.d@test.com, withdraw only the Psychologist application and
report its status afterwards. DB: applications row 4 flipped to Withdrawn
(only withdrawn + status change).
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

TASK_ID = "Chronicle Jobs--19"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "carol.d@test.com")
    check_account_section(j, t, "Applications")
    check_row_edited_only_in(j, initial_db, after_db, "applications", 4, ("withdrawn", "status"), label="withdraw")
    after_row = rows_where(after_db, "applications", "id = 4")[0]
    j.check("withdraw_state_correct", after_row["status"] == "Withdrawn" and int(after_row["withdrawn"]) == 1,
            f"after={after_row['status']} withdrawn={after_row['withdrawn']}")
    fa = final_answer(t)
    j.check("answer_has_status", contains_all(fa, ["Withdrawn"]), f"expected='Withdrawn' answer={fa[:200]!r}")


def main():
    from composed_grade import grade
    grade(19)


if __name__ == "__main__":
    main()
