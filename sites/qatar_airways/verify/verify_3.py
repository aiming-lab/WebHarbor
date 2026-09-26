#!/usr/bin/env python3
"""Verify Qatar Airways--3.

QR004 (London to Doha, 24 Sep 2026): En route, scheduled
departure 15:05, estimated arrival 23:47, Airbus A380-800. Earliest
London-Doha departure that day: QR104 at 08:25. The A380-800 fleet page:
First/Business/Economy cabins, 517 seats. Read-only task.
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

TASK_ID = "Qatar Airways--3"


SCHED_DEP = "15:05"
EST_ARR = "23:47"
EARLIEST_DEP = "08:25"
EARLIEST_FLIGHT = "QR104"
TOTAL_SEATS = 517


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_status_by_number",
                navigated_flight_status(traj, mode="number", number="QR004"),
                "required: flight-status by number QR004")
    judge.check("visited_status_by_route",
                navigated_flight_status(traj, mode="route", origin="LHR", dest="DOH"),
                "required: flight-status by route LHR->DOH")
    judge.check("visited_a380_fleet", navigated_fleet(traj, "Airbus-A380-800"),
                "required: /en/our-fleet/Airbus-A380-800.html")
    judge.check("answer_status", contains_all(answer, ["En route"]),
                "expected the current status En route")
    judge.check("answer_sched_dep", contains_time(answer, SCHED_DEP),
                f"expected scheduled departure {SCHED_DEP}")
    judge.check("answer_est_arr", contains_time(answer, EST_ARR),
                f"expected estimated arrival {EST_ARR}")
    judge.check("answer_aircraft", contains_all(answer, ["A380-800"]),
                "expected the aircraft Airbus A380-800")
    judge.check("answer_earliest_dep", contains_time(answer, EARLIEST_DEP),
                f"expected the earliest London-Doha departure {EARLIEST_DEP}")
    judge.check("answer_earliest_flight", contains_all(answer, [EARLIEST_FLIGHT]),
                f"expected the earliest flight {EARLIEST_FLIGHT}")
    judge.check("answer_cabins",
                contains_all(answer, ["First"]) and contains_all(answer, ["Business"])
                and contains_all(answer, ["Economy"]),
                "expected First, Business and Economy cabins")
    judge.check("answer_total_seats", contains_amount(answer, TOTAL_SEATS),
                f"expected the A380-800 total seat count {TOTAL_SEATS}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
