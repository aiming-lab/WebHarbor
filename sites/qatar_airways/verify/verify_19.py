#!/usr/bin/env python3
"""Verify Qatar Airways--19.

DOH->DXB for two on 2026-10-05: Economy Lite totals USD 280
vs Economy Comfort USD 430; the cheaper Economy Lite booking (Ravi Patel
+ Anaya Patel) costs 280 + 34 taxes = USD 314.
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

TASK_ID = "Qatar Airways--19"


LITE_TOTAL = 280
COMFORT_TOTAL = 430
BOOKED_TOTAL = 314
LEG_DATE = "2026-10-05"
PAX = [("Ravi", "Patel"), ("Anaya", "Patel")]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_search",
                navigated_search(traj, "DOH", "DXB", "Economy", adults=2),
                "required: /en/search-results.html?from=DOH&to=DXB&adults=2&cabin=Economy")
    judge.check("visited_pax_details", navigated_passenger_details(traj),
                "required: /en/booking/passenger-details.html")
    judge.check("visited_payment", navigated_payment(traj),
                "required: /en/booking/payment.html")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /en/booking/confirmation.html")
    added = added_booking_matching(after_db, initial_db, cabin="Economy",
                                   fare_type="ECO_LITE", adults=2, children=0,
                                   total=BOOKED_TOTAL, origin="DOH", dest="DXB",
                                   leg_date=LEG_DATE)
    judge.check("added_booking_row", added is not None,
                f"expected one added ECO_LITE booking DOH->DXB {LEG_DATE} for 2 adults, total {BOOKED_TOTAL}")
    if added:
        judge.check("pnr_in_answer", added["pnr"] in pnr_tokens(answer),
                    f"answer must quote the booking reference {added['pnr']!r}")
        pax = booking_passengers(after_db, added["id"])
        judge.check("two_passenger_rows",
                    len(pax) == 2,
                    "expected 2 passenger rows")
        judge.check("named_passengers",
                    any(p["first_name"] == "Ravi" and p["last_name"] == "Patel" for p in pax)
                    and any(p["first_name"] == "Anaya" and p["last_name"] == "Patel" for p in pax),
                    "expected passenger rows for Ravi Patel and Anaya Patel")
    judge.check("answer_lite_total", contains_amount(answer, LITE_TOTAL),
                f"expected the Economy Lite total USD {LITE_TOTAL} for two")
    judge.check("answer_comfort_total", contains_amount(answer, COMFORT_TOTAL),
                f"expected the Economy Comfort total USD {COMFORT_TOTAL} for two")
    judge.check("answer_booked_total", contains_amount(answer, BOOKED_TOTAL),
                f"expected the booked total USD {BOOKED_TOTAL}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
