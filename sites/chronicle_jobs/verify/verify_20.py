#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--20 (stateful (alice apply)).

Log in as alice.j@test.com, apply to 'Director of Client Solutions and
Support' with a short cover note, report the confirmation and the status in
the applications list. DB: exactly one applications row added (alice, job,
cover note >= 20 chars, Applied).
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

TASK_ID = "Chronicle Jobs--20"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "alice.j@test.com")
    check_visited_path(j, t, "visited_apply_page", "/apply/38023016/director-of-client-solutions-and-support")
    def _is_alice_apply(r):
        return (int(r["user_id"]) == 1 and int(r["job_id"]) == 120
                and len(str(r["cover_note"] or "")) >= 20 and r["status"] == "Applied" and not int(r["withdrawn"]))
    check_only_rows_added(j, initial_db, after_db, "applications", 1, predicate=_is_alice_apply, label="application")
    fa = final_answer(t)
    j.check("answer_reports_submission", contains_any(fa, ["submitted", "application"]),
            f"answer={fa[:200]!r}")
    j.check("answer_has_status", contains_all(fa, ["Applied"]), f"expected status='Applied' answer={fa[:200]!r}")


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
