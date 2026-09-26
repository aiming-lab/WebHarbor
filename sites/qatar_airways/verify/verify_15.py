#!/usr/bin/env python3
"""Verify Qatar Airways--15.

Baggage facts: Economy Comfort piece-concept 2 pieces up to
23kg (50lb) each; extra 23kg piece on Doha-Sao Paulo (over 8,000km) USD
140; Business Elite weight-concept 40kg (88lb); Economy Lite piece-concept
1 piece up to 23kg (50lb); Economy carry-on 1 piece up to 7kg (Help FAQ).
Read-only task.
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

TASK_ID = "Qatar Airways--15"


EXTRA_RATE = 140
CARRYON_KG = 7


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_baggage_comfort",
                navigated_baggage(traj, fare="Economy Comfort", route="americas"),
                "required: baggage checker Economy Comfort / piece concept")
    judge.check("visited_baggage_elite",
                navigated_baggage(traj, fare="Business Elite", route="weight"),
                "required: baggage checker Business Elite / weight concept")
    judge.check("visited_baggage_lite",
                navigated_baggage(traj, fare="Economy Lite", route="americas"),
                "required: baggage checker Economy Lite / piece concept")
    judge.check("visited_help", navigated_help(traj),
                "required: /en/help.html for the carry-on rules")
    judge.check("answer_eco_comfort",
                contains_amount(answer, 2) and contains_any(answer, ["23kg", "23 kg"]),
                "expected Economy Comfort 2 pieces up to 23kg each")
    judge.check("answer_extra_rate", contains_amount(answer, EXTRA_RATE),
                f"expected the extra-piece rate USD {EXTRA_RATE}")
    judge.check("answer_bus_elite",
                contains_any(answer, ["40kg", "40 kg", "88lb", "88 lb"]),
                "expected Business Elite 40kg (88lb) on weight concept")
    judge.check("answer_eco_lite",
                contains_all(answer, ["Lite"]) and
                (contains_all(answer, ["1 piece", "one piece"]) or contains_amount(answer, 1)),
                "expected Economy Lite 1 piece up to 23kg on piece concept")
    judge.check("answer_carryon", contains_amount(answer, CARRYON_KG),
                f"expected the Economy carry-on limit {CARRYON_KG}kg per piece")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
