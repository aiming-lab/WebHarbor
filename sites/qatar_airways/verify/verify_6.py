#!/usr/bin/env python3
"""Verify Qatar Airways--6.

david.k adds two extra 23kg pieces to QD77LW (First Elite,
DOH->SYD over 8,000km): per-piece fee USD 140, fee charged USD 280,
total 69,451 -> 69,731. First Elite on weight-concept routes includes
50kg (110lb).
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

TASK_ID = "Qatar Airways--6"


PNR = "QD77LW"
FEE = 280
PER_PIECE = 140
NEW_TOTAL = 69731


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_baggage_checker",
                navigated_baggage(traj, fare="First Elite", route="weight"),
                "required: baggage checker First Elite / weight concept")
    judge.check("visited_manage_lookup", navigated_manage_lookup(traj),
                "required: /en/manage-booking.html")
    judge.check("visited_manage_booking", navigated_manage_booking(traj, PNR),
                f"required: /en/manage-booking/{PNR}.html")
    booking = find_booking(after_db, PNR)
    judge.check("extra_bags_added",
                booking and booking["extra_bags"] == 2,
                f"expected extra_bags=2 on {PNR}; got {booking and booking['extra_bags']!r}")
    judge.check("fee_charged",
                booking and booking["total_paid"] == NEW_TOTAL,
                f"expected total {NEW_TOTAL} (69,451 + {FEE}); got {booking and booking['total_paid']!r}")
    judge.check("answer_first_elite_weight",
                contains_any(answer, ["50kg", "50 kg", "110lb", "110 lb"]),
                "expected the First Elite weight-concept allowance 50kg (110lb)")
    judge.check("answer_per_piece_fee", contains_amount(answer, PER_PIECE),
                f"expected the per-piece fee USD {PER_PIECE}")
    judge.check("answer_fee_charged", contains_amount(answer, FEE),
                f"expected the fee charged USD {FEE}")
    judge.check("answer_new_total", contains_amount(answer, NEW_TOTAL),
                f"expected the new total USD {NEW_TOTAL}")
    check_only_tables_changed(judge, initial_db, after_db, ("bookings",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
