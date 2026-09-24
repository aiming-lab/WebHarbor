#!/usr/bin/env python3
"""Verify Megabus--4.

Carol wants to cancel her New York-to-Toronto trip on October 4th. Sign in as carol.d@test.com (password TestPass123!), check whether the tracker reports a delay for her 5:15pm departure, then cancel booking W9C4FJ through Change trip. Confirm it appears among her cancelled trips, and explain the refund message and the total attached to the cancelled booking.
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
