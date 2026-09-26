#!/usr/bin/env python3
"""Verify Qatar Airways--4.

Route status DOH->SYD on 2026-09-24: QR908 on a Boeing 777-300ER
departing 20:05. Sydney guide Things to do starts with the Sydney
Opera House. Read-only task.
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

TASK_ID = "Qatar Airways--4"

DEP_TIME = "20:05"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_status_by_route",
                navigated_flight_status(traj, mode="route", origin="DOH", dest="SYD"),
                "required: /en/flight-status.html?mode=route&from=DOH&to=SYD")
    judge.check("visited_sydney_guide",
                navigated_destination_guide(traj, "flights-to-sydney"),
                "required: /en/destinations/flights-to-sydney.html")
    judge.check("answer_flight",
                contains_any(answer, ["QR908", "flight 908", "QR 908", "flight number 908"]),
                "expected flight QR908")
    judge.check("answer_aircraft", contains_all(answer, ["Boeing", "777"]),
                "expected aircraft 'Boeing 777-300ER'")
    judge.check("answer_dep_time", contains_time(answer, DEP_TIME),
                f"expected departure {DEP_TIME}")
    judge.check("answer_attraction", contains_all(answer, ["Sydney", "Opera", "House"]),
                "expected first attraction 'Sydney Opera House'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
