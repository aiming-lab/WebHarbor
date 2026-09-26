#!/usr/bin/env python3
"""Verify Qatar Airways--16.

Help facts: hard-of-hearing support +1 833 607 2675;
medical assistance form between 7 days and 48 hours before departure;
Oman firearms more than 19 days prior; proof-of-travel certificates up
to 12 months from the date of travel; infants carry one baby stroller
or collapsible carrycot at no additional cost. Read-only task.
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

TASK_ID = "Qatar Airways--16"


MEDICAL_DAYS = 7
MEDICAL_HOURS = 48
OMAN_DAYS = 19
CERT_MONTHS = 12


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_help", navigated_help(traj),
                "required: /en/help.html")
    judge.check("answer_support_number",
                contains_all(answer, ["833", "607", "2675"]),
                "expected the hard-of-hearing support number +1 833 607 2675")
    judge.check("answer_medical_window",
                contains_amount(answer, MEDICAL_DAYS) and contains_amount(answer, MEDICAL_HOURS),
                f"expected the medical form window {MEDICAL_DAYS} days / {MEDICAL_HOURS} hours")
    judge.check("answer_oman_firearms",
                contains_all(answer, ["Oman"]) and contains_amount(answer, OMAN_DAYS),
                f"expected the Oman firearms deadline {OMAN_DAYS} days")
    judge.check("answer_certificate_window",
                contains_amount(answer, CERT_MONTHS) and
                contains_any(answer, ["month", "months"]),
                f"expected certificates requestable up to {CERT_MONTHS} months after travel")
    judge.check("answer_infant_item",
                contains_any(answer, ["stroller", "carrycot"]),
                "expected the infant stroller / collapsible carrycot at no extra cost")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
