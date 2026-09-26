#!/usr/bin/env python3
"""Verify Qatar Airways--17.

Joining Privilege Club as Fiona Gray creates a Burgundy
member (membership number QRPC0000005, joined 2026-09-24, country
Ireland); Burgundy gives a 10% seat selection discount; Silver needs
150 Qpoints within 12 months.
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

TASK_ID = "Qatar Airways--17"


EMAIL = "fiona.gray@example.com"
FIRST = "Fiona"
LAST = "Gray"
COUNTRY = "Ireland"
SILVER = 150
SEAT_DISCOUNT = 10
JOIN_DATE = "2026-09-24"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_join", navigated_pc(traj, "join"),
                "required: /en/Privilege-Club/join.html")
    judge.check("visited_dashboard", navigated_pc(traj, "dashboard"),
                "required: /en/Privilege-Club/dashboard.html")
    judge.check("visited_tiers", navigated_pc(traj, "membership-tiers"),
                "required: /en/Privilege-Club/membership-tiers.html")
    member = user_by_email(after_db, EMAIL)
    judge.check("member_created",
                member and member["first_name"] == FIRST and member["last_name"] == LAST
                and member["tier"] == "Burgundy" and member["joined"] == JOIN_DATE,
                f"expected a new Burgundy member {FIRST} {LAST} joined {JOIN_DATE}; got "
                f"{member and (member['first_name'], member['last_name'], member['tier'], member['joined'])!r}")
    if member:
        judge.check("membership_number_in_answer",
                    member["membership_no"] in answer.replace(" ", ""),
                    f"answer must quote the membership number {member['membership_no']!r}")
        judge.check("country_saved",
                    (member["country"] or "").strip() == COUNTRY,
                    f"expected country {COUNTRY!r}; got {member['country']!r}")
    judge.check("answer_starting_tier", contains_all(answer, ["Burgundy"]),
                "expected the starting tier Burgundy")
    judge.check("answer_seat_discount", contains_amount(answer, SEAT_DISCOUNT),
                f"expected the Burgundy seat selection discount {SEAT_DISCOUNT}%")
    judge.check("answer_silver_threshold", contains_amount(answer, SILVER),
                f"expected the Silver threshold {SILVER} Qpoints")
    judge.check("answer_join_date", contains_all(answer, [JOIN_DATE]),
                f"expected the join date {JOIN_DATE}")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
