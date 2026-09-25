#!/usr/bin/env python3
"""Verify MTA--3.

Elevator serving the Woodlawn-bound 4 platform at 149 St-Grand Concourse out
since Wednesday morning: current status, reason, estimated return on the
elevator status page, then file a feedback report (Sam Ortiz,
sam.ortiz73@example.com) and report the new case number.

Frozen ground truth (seed DB): outage EL101 — "Transfer mezzanine to
Woodlawn-bound 4 platform and Bronx-bound 2/5 platform", ADA, out since
09/23/2026 10:55 AM, reason "Planned Work", estimated return 09/25/2026
10:00 PM, with alternative-route guidance (Manhattan-bound 4/5 to 161 St –
Yankee Stadium transfer, per the equipment registry). The feedback form
creates the first case after a clean reset: CS-26095598 (deterministic
next_ref on the pinned day).
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (FIRST_CASE_REF, added_rows, check_only_tables_changed, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_phrase, contains_ref, final_answer, navigated_elevator_search, navigated_to_path, run_verifier)

TASK_ID = "MTA--3"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_elevator_status_149",
                navigated_elevator_search(traj, "149 St-Grand Concourse"),
                "required: /elevator-escalator-status?station=149 St-Grand Concourse")
    judge.check("visited_feedback_form", navigated_to_path(traj, "/contact-us/feedback"),
                "required: /contact-us/feedback")
    judge.check("answer_elevator_el101", contains_phrase(answer, "el101"),
                "the outage elevator is EL101")
    judge.check("answer_reason_planned_work", contains_phrase(answer, "planned work"),
                "reason: Planned Work")
    judge.check("answer_eta_0925",
                contains_phrase(answer, "09/25/2026") or contains_phrase(answer, "september 25"),
                "estimated return 09/25/2026 10:00 PM")
    judge.check("answer_case_number", contains_ref(answer, FIRST_CASE_REF),
                f"the new case number is {FIRST_CASE_REF}")
    # DB after-state: exactly one feedback case added with the elevator category
    added = added_rows(after_db, initial_db, "feedback_cases", "case_ref")
    judge.check("one_case_added", len(added) == 1, f"added cases={[r['case_ref'] for r in added]!r}")
    if added:
        c = added[0]
        judge.check("added_case_ref", c["case_ref"] == FIRST_CASE_REF,
                    f"case_ref={c['case_ref']!r}, expected {FIRST_CASE_REF}")
        judge.check("added_case_category",
                    (c["category"] or "").lower() == "elevator or escalator outage",
                    f"category={c['category']!r}")
        judge.check("added_case_subject_or_message_about_elevator",
                    "el101" in (c["subject"] or "").lower() or "elevator" in (c["subject"] or "").lower()
                    or "elevator" in (c["message"] or "").lower(),
                    f"subject={c['subject']!r}")
        judge.check("added_case_status_open", c["status"] == "Open", f"status={c['status']!r}")
    judge.check("visited_ada_complaint_page",
                navigated_to_path(traj, "/accessibility/ada-complaint"),
                "required: /accessibility/ada-complaint")
    judge.check("answer_ada_filing_procedure",
                contains_any_phrase(answer, ["feedback form", "511"]),
                "ADA complaints: online feedback form (or 511 / the apps)")
    judge.check("answer_ada_case_ticket_number",
                contains_phrase(answer, "case ticket number"),
                "a case ticket number is issued once the case is logged")
    check_only_tables_changed(judge, initial_db, after_db, ("feedback_cases",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
