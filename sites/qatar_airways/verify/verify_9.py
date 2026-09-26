#!/usr/bin/env python3
"""Verify Qatar Airways--9.

Avios calculator DOH->JFK Business for a Gold member: 3,766 Avios
(10,765km/10 = 1,077 base x2 x1.75) and 431 Qpoints (10,765/25);
flight QR701 departs 08:00. Read-only task.
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

TASK_ID = "Qatar Airways--9"

AVIOS = 3766
QPOINTS = 431
DEP_TIME = "08:00"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_calculator", navigated_pc(traj, "avios-calculator"),
                "required: /en/Privilege-Club/avios-calculator.html")
    judge.check("calculator_inputs", entered_text_containing(traj, "JFK"),
                "required: JFK entered in the calculator")
    judge.check("answer_avios", contains_amount(answer, AVIOS),
                f"expected {AVIOS} Avios in the answer")
    judge.check("answer_qpoints", contains_amount(answer, QPOINTS),
                f"expected {QPOINTS} Qpoints in the answer")
    judge.check("answer_flight",
                contains_any(answer, ["QR701", "flight 701", "flight number 701", "QR 701"]),
                "expected flight QR701")
    judge.check("answer_dep_time", contains_time(answer, DEP_TIME),
                f"expected scheduled departure {DEP_TIME}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
