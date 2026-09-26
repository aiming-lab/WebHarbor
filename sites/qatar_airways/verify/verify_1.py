#!/usr/bin/env python3
"""Verify Qatar Airways--1.

Economy Classic round trip DOH->BKK: earliest outbound QR834 (02:00) on
2026-10-12 and earliest inbound QR837 (02:30) on 2026-10-26;
795 + 825 = 1620 + 194 taxes = USD 1814 total.
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

TASK_ID = "Qatar Airways--1"

TOTAL = 1814
OUT_FLIGHT = 834
RET_FLIGHT = 837
OUT_DATE = "2026-10-12"
RET_DATE = "2026-10-26"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_search",
                navigated_search(traj, "DOH", "BKK", "Economy"),
                "required: DOH->BKK Economy search with the return date")
    judge.check("visited_return_picker", navigated_select_return(traj),
                "required: /en/booking/select-return.html")
    judge.check("visited_pax_details", navigated_passenger_details(traj),
                "required: /en/booking/passenger-details.html")
    judge.check("visited_payment", navigated_payment(traj),
                "required: /en/booking/payment.html")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /en/booking/confirmation.html")
    added = added_booking_matching(after_db, initial_db, cabin="Economy",
                                   fare_type="ECO_CLASSIC", adults=1, children=0,
                                   total=TOTAL, origin="DOH", dest="BKK",
                                   leg_date=OUT_DATE,
                                   flight_numbers=[OUT_FLIGHT, RET_FLIGHT])
    judge.check("added_booking_row", added is not None,
                f"expected ECO_CLASSIC round-trip booking on QR{OUT_FLIGHT}/QR{RET_FLIGHT}, total {TOTAL}")
    if added:
        legs = booking_legs(after_db, added["id"])
        judge.check("earliest_out_and_in",
                   sorted(l["flight_number"] for l in legs) == sorted([OUT_FLIGHT, RET_FLIGHT]),
                   f"expected earliest outbound QR{OUT_FLIGHT} and earliest inbound QR{RET_FLIGHT}; "
                   f"got {[l['flight_number'] for l in legs]}")
        judge.check("return_leg_dated",
                    any(l["leg_date"] == RET_DATE for l in legs),
                    f"return leg must be dated {RET_DATE}")
        judge.check("pnr_in_answer", added["pnr"] in pnr_tokens(answer),
                    f"answer must quote the booking reference {added['pnr']!r}")
    judge.check("answer_total", contains_amount(answer, TOTAL),
                f"expected total USD {TOTAL} in the answer")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
