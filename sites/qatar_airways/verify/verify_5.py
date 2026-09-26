#!/usr/bin/env python3
"""Verify Qatar Airways--5.

Cancel seeded booking QR92XN (alice's DOH->CDG trip on QR041); her other
trip QK17TP must stay confirmed.
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

TASK_ID = "Qatar Airways--5"

PNR = "QR92XN"
KEEP_PNR = "QK17TP"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_manage_lookup", navigated_manage_lookup(traj),
                "required: /en/manage-booking.html")
    judge.check("visited_manage_booking", navigated_manage_booking(traj, PNR),
                f"required: /en/manage-booking/{PNR}.html")
    cancelled = find_booking(after_db, PNR)
    judge.check("booking_cancelled",
                cancelled and cancelled["status"] == "cancelled",
                f"expected {PNR} status 'cancelled'; got {cancelled and cancelled['status']!r}")
    kept = find_booking(after_db, KEEP_PNR)
    judge.check("other_trips_unchanged",
                kept and kept["status"] == "confirmed",
                f"expected {KEEP_PNR} still confirmed; got {kept and kept['status']!r}")
    judge.check("answer_names_trip",
                contains_any(answer, ["QR92XN", "Paris", "CDG"]),
                "answer must name the cancelled trip")
    judge.check("answer_cancellation_note",
                contains_any(answer, ["cancelled", "canceled"]) and
                contains_any(answer, ["refund", "payment method", "processed"]),
                "expected the cancellation message (refund to the original payment method)")
    check_only_tables_changed(judge, initial_db, after_db, ("bookings",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
