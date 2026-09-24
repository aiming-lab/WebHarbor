#!/usr/bin/env python3
"""Verify Ohio.gov--9.

Consumer complaint chain: file a romance-scam complaint (scam type "Romance
scam", amount 450, short description) without logging in, report the
confirmation message and the dedicated romance scam hotline number shown on
the report page.

Frozen ground truth: the seed has exactly one scam report (David's); after the
task the scam_reports table gains exactly one row — scam_type "Romance scam",
amount "450", full_name Rosa Parks, non-empty description, user_id NULL. The
report page shows the dedicated romance scam hotline 1-855-961-7226 and the
confirmation flash says the complaint was submitted to the Ohio Attorney
General's office.

Review note (F-NAV-1): /report-scam currently has no guest-visible link (the
only link lives in the logged-in account sidebar). The navigation gate stays
strict so the grading contract is meaningful once the link is added.
"""
from verify_lib import (check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "Ohio.gov--9"
REPORT_PATH = "/report-scam"
SCAM_TYPE = "Romance scam"
AMOUNT = "450"
HOTLINE = "1-855-961-7226"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gate: the report form must have been opened
    check_visited_path(judge, traj, "visited_report_scam_form", REPORT_PATH)
    # DB after-state: exactly one new scam report with the task fields
    from verify_lib import added_scam_reports
    added = added_scam_reports(after_db, initial_db)
    judge.check("one_report_added", len(added) == 1, f"added={len(added)}")
    if added:
        r = added[0]
        judge.check("added_report_scam_type", (r["scam_type"] or "") == SCAM_TYPE,
                   f"scam_type={r['scam_type']!r}")
        judge.check("added_report_amount", (r["amount"] or "").strip() == AMOUNT,
                   f"amount={r['amount']!r}")
        judge.check("added_report_description",
                   bool((r["description"] or "").strip()) and len(r["description"].strip()) >= 10,
                   f"description={r['description']!r}")
        judge.check("added_report_guest", r["user_id"] is None,
                   f"user_id={r['user_id']!r} (guest complaint)")
    check_only_tables_changed(judge, initial_db, after_db, ("scam_reports",))
    # answer: confirmation message + hotline
    judge.check("answer_confirmation",
                contains_phrase(answer, "attorney general")
                and contains_phrase(answer, "confirmation"),
                "expected: complaint submitted to the Ohio Attorney General's office; keep your confirmation number")
    judge.check("answer_hotline",
                contains_phrase(answer, "1-855-961-7226"),
                "expected romance scam hotline 1-855-961-7226")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
