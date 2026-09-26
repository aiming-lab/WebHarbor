#!/usr/bin/env python3
"""Verify Qatar Airways--10.

320 Qpoints within 12 months qualifies for Gold (300 threshold),
oneworld Sapphire; Platinum needs 600 within 12 months (280 more); Gold
extra baggage 20kg or one piece. Real accounts: bob.c is Silver, 90 Qpoints
from Gold; alice.j is Gold, 185 Qpoints from Platinum; Bob is closest to
his next tier. Read-only task.
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

TASK_ID = "Qatar Airways--10"


GOLD_THRESHOLD = 300
PLATINUM_THRESHOLD = 600
BOB_TO_NEXT = 90
ALICE_TO_NEXT = 185


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_identity(judge, initial_db)
    judge.check("visited_tiers", navigated_pc(traj, "membership-tiers"),
                "required: /en/Privilege-Club/membership-tiers.html")
    judge.check("signed_in_bob", entered_text_containing(traj, "bob.c@test.com"),
                "required: sign-in as bob.c@test.com")
    judge.check("signed_in_alice", entered_text_containing(traj, "alice.j@test.com"),
                "required: sign-in as alice.j@test.com")
    judge.check("visited_dashboard", navigated_pc(traj, "dashboard"),
                "required: /en/Privilege-Club/dashboard.html")
    judge.check("answer_gold", contains_all(answer, ["Gold"]),
                "expected tier 'Gold'")
    judge.check("answer_oneworld", contains_all(answer, ["Sapphire"]),
                "expected oneworld 'Sapphire'")
    judge.check("answer_next_tier",
                contains_all(answer, ["Platinum"]) and
                (contains_amount(answer, PLATINUM_THRESHOLD) or contains_amount(answer, 280)),
                "expected Platinum at 600 Qpoints (280 more)")
    judge.check("answer_baggage",
                (contains_amount(answer, 20) and contains_any(answer, ["kg", "20kg"])) or
                contains_all(answer, ["one", "piece"]),
                "expected Gold extra baggage 20kg or one piece")
    judge.check("answer_bob_tier", contains_all(answer, ["Silver"]),
                "expected Bob's tier Silver")
    judge.check("answer_bob_to_next", contains_amount(answer, BOB_TO_NEXT),
                f"expected Bob {BOB_TO_NEXT} Qpoints from Gold")
    judge.check("answer_alice_to_next", contains_amount(answer, ALICE_TO_NEXT),
                f"expected Alice {ALICE_TO_NEXT} Qpoints from Platinum")
    judge.check("answer_closest_is_bob",
                contains_all(answer, ["Bob"]) and
                contains_any(answer, ["closest", "closest to", "nearest"]),
                "expected Bob named as closest to the next tier")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
