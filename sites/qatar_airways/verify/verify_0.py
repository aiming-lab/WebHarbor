#!/usr/bin/env python3
"""Verify Qatar Airways--0.

Cheapest Economy Lite DOH->LHR for two adults on 2026-10-08: USD 665/pax
on QR105, QR119 and QR007 (every other flight is dearer); 2 x 665 = 1330
+ 160 taxes = USD 1490 total. Any of the three tied flights is correct.
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

TASK_ID = "Qatar Airways--0"

ROUTE = ("DOH", "LHR")
LEG_DATE = "2026-10-08"
CHEAPEST_PER_PAX = 665
TOTAL = 1490
TIED_FLIGHTS = (105, 119, 7)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_search",
                navigated_search(traj, "DOH", "LHR", "Economy", adults=2),
                "required: /en/search-results.html?from=DOH&to=LHR&cabin=Economy&adults=2")
    judge.check("visited_pax_details", navigated_passenger_details(traj),
                "required: /en/booking/passenger-details.html")
    judge.check("visited_payment", navigated_payment(traj),
                "required: /en/booking/payment.html")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /en/booking/confirmation.html")
    added = added_booking_matching(after_db, initial_db, cabin="Economy",
                                   fare_type="ECO_LITE", adults=2, children=0,
                                   total=TOTAL, origin="DOH", dest="LHR",
                                   leg_date=LEG_DATE)
    judge.check("added_booking_row", added is not None,
                f"expected one added ECO_LITE booking DOH->LHR {LEG_DATE} for 2 adults, total {TOTAL}")
    if added:
        legs = booking_legs(after_db, added["id"])
        judge.check("cheapest_flight_selected",
                   sorted(l["flight_number"] for l in legs) in [[f] for f in TIED_FLIGHTS],
                   f"expected one of the tied cheapest flights {TIED_FLIGHTS} "
                   f"(Economy Lite USD {CHEAPEST_PER_PAX}); got {[l['flight_number'] for l in legs]}")
        judge.check("pnr_in_answer", added["pnr"] in pnr_tokens(answer),
                    f"answer must quote the booking reference {added['pnr']!r}")
        judge.check("two_passenger_rows",
                    len(booking_passengers(after_db, added["id"])) == 2,
                    "expected 2 passenger rows")
    judge.check("answer_total", contains_amount(answer, TOTAL),
                f"expected total USD {TOTAL} in the answer")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
