#!/usr/bin/env python3
"""Verify Marriott--5.

Sign in as alice.j@test.com. Reservation ACCEDGHDDR under guest Alice Johnson:
from the trips page, open that reservation's hotel page and report its listed
check-in time. Then look the reservation up on Find My Reservation and report the
hotel, room type, check-in date, and total. Finally cancel it and look it up again
to report the status shown.

Frozen ground truth (seed DB): ACCEDGHDDR = Courtyard by Marriott Atlanta Downtown
(marsha ATLDO), Guest Room, 1 King Bed, check-in 11/02/2026 -> 11/04/2026, total
$290, check-in time 16:00 (rendered "4:00 pm"); cancel flips status to canceled.
"""
from verify_lib import (Judge, canceled_among, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_amount, navigated_to_path_any,
                        contains_any, contains_date_phrase, contains_phrase, contains_slash_date,
                        contains_time, final_answer, navigated_hotel_overview, navigated_to,
                        run_verifier)

TASK_ID = "Marriott--5"
CONF = "ACCEDGHDDR"
HOTEL = "Courtyard by Marriott Atlanta Downtown"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("visited_account_trips",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account/trips page (either route alias)")
    judge.check("visited_hotel_page", navigated_hotel_overview(traj, "courtyard-atlanta-downtown"),
                "required: the reservation hotel's overview page (courtyard-atlanta-downtown)")
    judge.check("visited_lookup_twice", navigated_to(traj, "/reservation/lookupReservation.mi", times=2),
                "required: Find My Reservation opened at least twice (lookup + re-check after cancel)")
    # answer: check-in time + lookup facts + post-cancel status
    judge.check("answer_checkin_time", contains_time(answer, 4, "00", "pm"),
                "expected check-in time 4:00 pm")
    judge.check("answer_hotel", contains_phrase(answer, "Courtyard by Marriott Atlanta Downtown"),
                "expected the hotel name")
    judge.check("answer_room_type", contains_phrase(answer, "Guest Room, 1 King Bed"),
                "expected room type Guest Room, 1 King Bed")
    judge.check("answer_checkin_date",
                contains_date_phrase(answer, "November 2, 2026") or contains_slash_date(answer, 11, 2, 2026),
                "expected check-in date Nov 02, 2026")
    judge.check("answer_total", contains_amount(answer, 290),
                "expected total $290")
    judge.check("answer_canceled_status", contains_any(answer, ["canceled", "cancelled"]),
                "expected the post-cancel status to be reported as Canceled")
    # DB after-state: exactly the ACCEDGHDDR status flip, nothing else
    judge.check("accedghddr_canceled", canceled_among(initial_db, after_db, CONF),
                f"expected {CONF} status confirmed -> canceled")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
