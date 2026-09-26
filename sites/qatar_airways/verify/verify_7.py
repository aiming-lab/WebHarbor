#!/usr/bin/env python3
"""Verify Qatar Airways--7.

Check in seeded booking QC08BV (QR701 DOH->JFK, dep 08:00): seats 30A/30B
are preferred-row seats on the 777-300ER -> 2 x USD 30 fees, total
6,787 + 60 = 6,847; gate F22, boarding 07:20.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_lib import (Judge, added_booking_matching, booking_legs,
                        booking_passengers, check_only_tables_changed, check_read_only,
                        check_seed_identity, check_trajectory_identity, contains_all,
                        contains_any, contains_amount, contains_time,
                        entered_text_containing, final_answer, find_booking,
                        navigated_baggage, navigated_boarding_pass, navigated_checkin,
                        navigated_checkin_lookup, navigated_confirmation,
                        navigated_destination_guide, navigated_destinations,
                        navigated_fleet, navigated_flight_status, navigated_help,
                        navigated_manage_booking, navigated_manage_lookup,
                        navigated_offer, navigated_passenger_details, navigated_payment,
                        navigated_pc, navigated_search, navigated_select_return,
                        pnr_tokens, row_delta, run_verifier, user_by_email)

TASK_ID = "Qatar Airways--7"

PNR = "QC08BV"
SEAT_FEES = 60
NEW_TOTAL = 6847
GATE = "F22"
BOARDING = "07:20"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_checkin", navigated_checkin(traj, PNR),
                f"required: /en/check-in/{PNR}.html")
    judge.check("visited_boarding_pass", navigated_boarding_pass(traj, PNR),
                f"required: /en/check-in/{PNR}/boarding-pass.html")
    booking = find_booking(after_db, PNR)
    judge.check("checked_in",
                booking and booking["checked_in"] == 1,
                f"expected checked_in=1; got {booking and booking['checked_in']!r}")
    pax = booking_passengers(after_db, booking["id"]) if booking else []
    seats = sorted(p["seat_out"] or "" for p in pax)
    judge.check("seats_assigned", seats == ["30A", "30B"],
                f"expected seats 30A/30B; got {[(p['first_name'], p['seat_out']) for p in pax]}")
    judge.check("seat_fees_charged",
                booking and booking["total_paid"] == NEW_TOTAL,
                f"expected total {NEW_TOTAL} (6,787 + {SEAT_FEES}); got {booking and booking['total_paid']!r}")
    judge.check("answer_gate", contains_all(answer, [GATE]),
                f"expected boarding gate {GATE}")
    judge.check("answer_boarding_time", contains_time(answer, BOARDING),
                f"expected boarding time {BOARDING}")
    judge.check("answer_seat_fees", contains_amount(answer, SEAT_FEES),
                f"expected seat fees USD {SEAT_FEES} in the answer")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
