#!/usr/bin/env python3
"""Verify Qatar Airways--8.

bob.c upgrades QB55MD (DOH->BKK Economy) to Business with
Avios: cost 1,948, balance shown on the booking page 15,300, dashboard
balance afterwards 13,352, booking shows Business, recent activity
"Upgrade to Business Class on QR826" -1,948 Avios.
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

TASK_ID = "Qatar Airways--8"


PNR = "QB55MD"
COST = 1948
BALANCE_BEFORE = 15300
BALANCE_AFTER = 13352
BOB = "bob.c@test.com"
ACTIVITY_DESC = "Upgrade to Business Class on QR826"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_login", navigated_pc(traj, "login"),
                "required: Privilege Club login")
    judge.check("visited_manage_booking", navigated_manage_booking(traj, PNR),
                f"required: /en/manage-booking/{PNR}.html")
    judge.check("visited_dashboard", navigated_pc(traj, "dashboard"),
                "required: /en/Privilege-Club/dashboard.html")
    booking = find_booking(after_db, PNR)
    judge.check("upgraded_to_business",
                booking and booking["cabin"] == "Business" and booking["avios_redeemed"] == COST,
                f"expected {PNR} cabin='Business', avios_redeemed={COST}; "
                f"got {booking and (booking['cabin'], booking['avios_redeemed'])!r}")
    member = user_by_email(after_db, BOB)
    judge.check("avios_debited",
                member and member["avios"] == BALANCE_AFTER,
                f"expected bob's balance {BALANCE_AFTER}; got {member and member['avios']!r}")
    new_acts = row_delta(initial_db, after_db, "activities", "id")
    judge.check("redemption_activity_row",
                len(new_acts) == 1 and ACTIVITY_DESC in new_acts[0]["description"]
                and new_acts[0]["avios"] == -COST,
                f"expected one new activity {ACTIVITY_DESC!r} -{COST}; got {new_acts!r}")
    judge.check("answer_cost", contains_amount(answer, COST),
                f"expected the upgrade cost {COST} Avios in the answer")
    judge.check("answer_balance_before", contains_amount(answer, BALANCE_BEFORE),
                f"expected the balance shown on the booking page ({BALANCE_BEFORE})")
    judge.check("answer_cabin_after", contains_all(answer, ["Business"]),
                "expected the booking's cabin class afterwards (Business)")
    judge.check("answer_balance_after", contains_amount(answer, BALANCE_AFTER),
                f"expected the dashboard Avios balance ({BALANCE_AFTER})")
    judge.check("answer_activity_entry",
                contains_all(answer, ["Upgrade", "QR826"]),
                "expected the recent-activity entry describing the redemption")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "users", "activities"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
