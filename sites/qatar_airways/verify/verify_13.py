#!/usr/bin/env python3
"""Verify Qatar Airways--13.

MotoGP promo code MOTOGP26 takes 10% off the fare; one-adult Economy
Classic DOH->LHR 2026-10-08 totals are frozen per flight in
PER_FLIGHT (discount, total).
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

TASK_ID = "Qatar Airways--13"

PROMO = "MOTOGP26"
LEG_DATE = "2026-10-08"
# flight number -> (discount, total) for one adult Economy Classic DOH->LHR
# with the 10% promo applied (frozen from the seed fare engine).
PER_FLIGHT = {1: (79, 796), 3: (82, 821), 7: (78, 792), 15: (79, 796),
              103: (83, 837), 105: (78, 792), 119: (78, 792)}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_offers", navigated_offer(traj),
                "required: /en/offers.html")
    judge.check("visited_offer_detail", navigated_offer(traj, "motogp-adventures"),
                "required: /en/offers/motogp-adventures.html")
    judge.check("visited_search_with_promo",
                navigated_search(traj, "DOH", "LHR", "Economy", promo=PROMO),
                f"required: search results carrying promo={PROMO}")
    judge.check("visited_pax_details", navigated_passenger_details(traj),
                "required: passenger details")
    judge.check("visited_payment", navigated_payment(traj),
                "required: payment")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: confirmation")
    added = added_booking_matching(after_db, initial_db, cabin="Economy",
                                   fare_type="ECO_CLASSIC", adults=1, children=0,
                                   promo_code=PROMO, origin="DOH", dest="LHR",
                                   leg_date=LEG_DATE)
    judge.check("added_booking_row", added is not None,
                f"expected ECO_CLASSIC DOH->LHR {LEG_DATE} booking with promo {PROMO}")
    if added:
        legs = booking_legs(after_db, added["id"])
        flight_no = legs[0]["flight_number"] if legs else None
        expected = PER_FLIGHT.get(flight_no)
        judge.check("total_matches_flight",
                   expected and added["total_paid"] == expected[1],
                   f"flight {flight_no}: expected total {expected and expected[1]}; got {added['total_paid']}")
        judge.check("pnr_in_answer", added["pnr"] in pnr_tokens(answer),
                    f"answer must quote the booking reference {added['pnr']!r}")
        if expected:
            judge.check("answer_discount", contains_amount(answer, expected[0]),
                        f"expected discount USD {expected[0]} in the answer")
            judge.check("answer_total", contains_amount(answer, expected[1]),
                        f"expected total USD {expected[1]} in the answer")
    judge.check("answer_promo", contains_all(answer, [PROMO]),
                f"expected promo code {PROMO} in the answer")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
