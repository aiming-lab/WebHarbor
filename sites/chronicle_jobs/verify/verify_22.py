#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--22 (stateful (anonymous alert)).

Create a Weekly job alert (no account) for 'registrar' near Chicago with
casey.r@test.com; report the confirmation. DB: exactly one job_alerts row
added (anonymous, registrar, Chicago, Weekly).
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

TASK_ID = "Chronicle Jobs--22"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_visited_path(j, t, "visited_new_alert", "/newalert")
    def _is_alert(r):
        return (r["user_id"] is None and "casey.r@test.com" in str(r["email"]).lower()
                and "registrar" in str(r["keywords"]).lower() and "chicago" in str(r["location"]).lower()
                and str(r["frequency"]) == "Weekly")
    check_only_rows_added(j, initial_db, after_db, "job_alerts", 1, predicate=_is_alert, label="alert")
    fa = final_answer(t)
    j.check("answer_reports_confirmation",
            contains_any(fa, ["alert created", "will be sent", "matching your criteria"]),
            f"answer={fa[:200]!r}")
    j.check("answer_has_email", contains_all(fa, ["casey.r@test.com"]), f"expected email in answer answer={fa[:200]!r}")


def main():
    from composed_grade import grade
    grade(22)


if __name__ == "__main__":
    main()
