#!/usr/bin/env python3
"""Verify Marriott--6.

Sign in as david.k@test.com. More than one upcoming trip: cancel the upcoming
reservation with the earliest check-in date, look it up again to confirm it shows
as canceled and report the cancellation message; then look up the remaining
confirmed upcoming trip and report its hotel, check-in date, and total, plus your
Bonvoy member tier.

Frozen ground truth (seed DB): david's upcoming trips = BRQEBMMFAQ (Residence Inn
by Marriott Atlanta Downtown, 10/11/2026, earliest) and LDNNPGBDCP (Courtyard by
Marriott Austin Downtown/Convention Center, 10/25/2026 -> 10/27/2026, $380);
member tier Platinum Elite; the seeded past stays (HJAGPAEJPQ, NRRQMNKHCQ) are NOT
upcoming and must not be the canceled one.
"""
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
    judge.check("visited_lookup_twice", navigated_to(traj, "/reservation/lookupReservation.mi", times=2),
                "required: Find My Reservation opened at least twice (cancel flow + remaining trip)")
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
    judge.check("answer_member_tier", contains_phrase(answer, "Platinum Elite"),
                "expected Bonvoy member tier Platinum Elite")
    # DB after-state: exactly the BRQEBMMFAQ status flip, nothing else
    judge.check("earliest_upcoming_canceled", canceled_among(initial_db, after_db, EARLIEST_CONF),
                f"expected {EARLIEST_CONF} status confirmed -> canceled")
    judge.check("remaining_trip_untouched", not canceled_among(initial_db, after_db, REMAINING_CONF),
                f"expected {REMAINING_CONF} to remain confirmed")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
