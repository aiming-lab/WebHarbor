#!/usr/bin/env python3
"""Verify Megabus--4.

Log in as carol.d@test.com; check the tracker for her confirmed NY->TOR booking
on 2026-10-04 (is the 5:15pm departure delayed?); then look up W9C4FJ under
Change trip, cancel it, and report the exact confirmation message including
what happens to the money, plus the total the cancelled booking shows under
her past and cancelled trips.

Frozen ground truth (seed DB): carol has two Toronto-touching bookings —
W9C4FJ (NY->TOR 2026-10-04 17:15, confirmed, total 84.29) and B7L2MX (NY->TOR
2026-10-04 20:00, already cancelled, total 84.04). Only W9C4FJ is the
cancellable confirmed one. The tracker shows the 2026-10-04 NY->TOR services
(05:15, 17:15, 20:00) all On time — the 5:15pm departure is NOT delayed. The
flash message reads: "Booking W9C4FJ was cancelled. A refund credit will be
emailed to you within 5-7 business days." The DB status must flip to
cancelled; B7L2MX must remain untouched.
"""
from verify_lib import (booking_by_reference, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, contains_time, final_answer, navigated_to_path,
                        run_verifier)
TASK_ID = "Megabus--4"
REF = "W9C4FJ"
MESSAGE = "Booking W9C4FJ was cancelled. A refund credit will be emailed to you within 5-7 business days."
CANCELLED_TOTAL = 84.29


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    # navigation gates: tracker pre-check, account area, manage-booking lookup + cancel
    check_visited_path(judge, traj, "visited_tracker", "/journey-planner/track")
    judge.check("visited_account", navigated_to_path(traj, "/account-management"),
                "required_path=/account-management")
    judge.check("visited_manage_booking", navigated_to_path(traj, "/journey-planner/manage-booking"),
                "required_path=/journey-planner/manage-booking")
    # answer: tracker status for the 17:15 departure + cancel message + cancelled-list total
    judge.check("answer_tracker_515pm_on_time",
                contains_time(answer, "17:15") and contains_phrase(answer, "on time"),
                "the 5:15pm NY->TOR departure is On time on the tracker (not delayed)")
    judge.check("answer_quotes_cancel_message",
                contains_phrase(answer, "was cancelled")
                and contains_phrase(answer, "refund credit")
                and contains_phrase(answer, "5-7 business days"),
                f"expected the exact flash message: {MESSAGE!r}")
    judge.check("answer_cancelled_total", contains_amount(answer, CANCELLED_TOTAL),
                f"expected the cancelled booking's total ${CANCELLED_TOTAL} under past and cancelled trips")
    # DB after-state: W9C4FJ cancelled, B7L2MX untouched, totals unchanged
    b = booking_by_reference(after_db, REF)
    judge.check("booking_cancelled", b is not None and b["status"] == "cancelled",
                f"reference={REF}, status={b['status'] if b else None!r}")
    other = booking_by_reference(after_db, "B7L2MX")
    judge.check("other_booking_untouched",
                other is not None and other["status"] == "cancelled" and abs(other["total"] - 84.04) < 0.011,
                f"B7L2MX status={other['status'] if other else None!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("bookings",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
