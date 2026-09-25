#!/usr/bin/env python3
"""Sign in as david.k@test.com (password TestPass123!). I need to drop the earliest of my upcoming trips. Identify and cancel that booking, keeping my later trip intact. Confirm which reservation was canceled and summarize the remaining confirmed trip's hotel, check-in date and total so I can update my itinerary."""
from verify_lib import (Judge, canceled_among, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_date_phrase, contains_phrase, contains_slash_date, final_answer,
                        navigated_to, navigated_to_path_any, run_verifier)

TASK_ID = "Marriott--6"
EARLIEST_CONF = "BRQEBMMFAQ"
REMAINING_CONF = "LDNNPGBDCP"
REMAINING_HOTEL = "Courtyard by Marriott Austin Downtown/Convention Center"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "david.k@test.com")
    judge.check("visited_account_trips",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account/trips page (either route alias)")
    # answer: cancellation message names the earliest-upcoming confirmation number
    judge.check("answer_cancel_message", contains_phrase(answer, EARLIEST_CONF),
                f"expected the cancellation message to name reservation {EARLIEST_CONF} "
                "(the earliest UPCOMING check-in; the past stays are not upcoming)")
    judge.check("answer_remaining_hotel", contains_phrase(answer, "Austin Downtown"),
                "expected the remaining trip hotel: Courtyard by Marriott Austin Downtown/Convention Center")
    judge.check("answer_remaining_checkin",
                contains_date_phrase(answer, "October 25, 2026") or contains_slash_date(answer, 10, 25, 2026),
                "expected remaining trip check-in date Oct 25, 2026")
    judge.check("answer_remaining_total", contains_amount(answer, 380),
                "expected remaining trip total $380")
    # DB after-state: exactly the BRQEBMMFAQ status flip, nothing else
    judge.check("earliest_upcoming_canceled", canceled_among(initial_db, after_db, EARLIEST_CONF),
                f"expected {EARLIEST_CONF} status confirmed -> canceled")
    judge.check("remaining_trip_untouched", not canceled_among(initial_db, after_db, REMAINING_CONF),
                f"expected {REMAINING_CONF} to remain confirmed")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
