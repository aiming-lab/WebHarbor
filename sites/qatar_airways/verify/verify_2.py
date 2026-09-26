#!/usr/bin/env python3
"""Verify Qatar Airways--2.

Alice (Gold, QRPC0004217, 48,250 Avios) books Business Classic DOH->CDG
on QR041 (2026-11-02): fare 7,960 + 955 taxes = USD 8,915; earns 1,740
Avios (4,974km/10 = 498 base x2 Business x1.75 Gold) -> balance 49,990.
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

TASK_ID = "Qatar Airways--2"

ALICE = "alice.j@test.com"
PC_NUMBER = "QRPC0004217"
TOTAL = 8915
EARNED_AVIOS = 1740
BALANCE_AFTER = 49990
LEG_DATE = "2026-11-02"
FLIGHT = 41


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_search",
                navigated_search(traj, "DOH", "CDG", "Business"),
                "required: DOH->CDG Business search")
    judge.check("visited_pax_details", navigated_passenger_details(traj),
                "required: /en/booking/passenger-details.html")
    judge.check("pc_number_entered",
                entered_text_containing(traj, PC_NUMBER),
                f"required: Privilege Club number {PC_NUMBER} entered during booking")
    judge.check("visited_payment", navigated_payment(traj),
                "required: /en/booking/payment.html")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /en/booking/confirmation.html")
    added = added_booking_matching(after_db, initial_db, cabin="Business",
                                   fare_type="BUS_CLASSIC", adults=1, children=0,
                                   total=TOTAL, origin="DOH", dest="CDG",
                                   leg_date=LEG_DATE, flight_numbers=[FLIGHT],
                                   pc_number=PC_NUMBER)
    judge.check("added_booking_row", added is not None,
                f"expected BUS_CLASSIC DOH->CDG {LEG_DATE} booking carrying {PC_NUMBER}, total {TOTAL}")
    member = user_by_email(after_db, ALICE)
    judge.check("avios_credited",
                member and member["avios"] == BALANCE_AFTER,
                f"expected alice's Avios balance {BALANCE_AFTER} (48250 + {EARNED_AVIOS}); "
                f"got {member and member['avios']!r}")
    if added:
        judge.check("pnr_in_answer", added["pnr"] in pnr_tokens(answer),
                    f"answer must quote the booking reference {added['pnr']!r}")
    judge.check("answer_total", contains_amount(answer, TOTAL),
                f"expected total USD {TOTAL} in the answer")
    judge.check("answer_balance", contains_amount(answer, BALANCE_AFTER),
                f"expected the Avios balance afterwards ({BALANCE_AFTER}) in the answer")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_legs", "passengers",
                               "users", "activities"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
