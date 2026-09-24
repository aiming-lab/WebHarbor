#!/usr/bin/env python3
"""Verify Megabus--19.

Book the cheapest bus from Toronto to Montreal on October 3rd for one traveler as a guest checkout with the email yuki.tanaka@example.com. Enable text message travel updates in the basket and pay with any valid card. Report the order reference and the total charged, broken down by fare, booking fee and SMS fee.
"""
from verify_lib import (Judge, added_bookings, booking_journeys_of, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, final_answer, journey_of, navigated_confirmation,
                        navigated_journeys, run_verifier)

TASK_ID = "Megabus--19"
TOR_ID, MTL_ID = 145, 279
CHEAPEST = 71.99
FARE, FEE, SMS = 71.99, 3.99, 0.25
TOTAL = 76.23
EMAIL = "yuki.tanaka@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_journeys_results",
                navigated_journeys(traj, TOR_ID, MTL_ID, "2026-10-03"),
                "required: journeys TOR→MTL on 2026-10-03")
    check_visited_path(judge, traj, "visited_basket", "/journey-planner/basket")
    check_visited_path(judge, traj, "visited_passenger_details", "/journey-planner/passenger-details")
    check_visited_path(judge, traj, "visited_payment", "/journey-planner/payment")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /journey-planner/confirmation/<ref>")
    judge.check("answer_fare", contains_amount(answer, FARE), f"expected fare ${FARE}")
    judge.check("answer_booking_fee", contains_amount(answer, FEE), f"expected booking fee ${FEE}")
    judge.check("answer_sms_fee", contains_amount(answer, SMS), f"expected SMS fee ${SMS}")
    judge.check("answer_total", contains_amount(answer, TOTAL), f"expected total ${TOTAL}")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1, f"added={[r['reference'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["email"] or "").lower() == EMAIL, f"email={b['email']!r}")
        judge.check("added_booking_sms", b["sms_updates"] == 1, f"sms_updates={b['sms_updates']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["reference"]),
                    f"answer must quote the created order reference {b['reference']!r}")
        bjs = booking_journeys_of(after_db, b["id"])
        judge.check("added_booking_journeys", len(bjs) == 1 and bjs[0]["passengers"] == 1,
                    f"booking_journeys={bjs!r}")
        if bjs:
            j = journey_of(after_db, bjs[0]["journey_id"])
            judge.check("booked_cheapest_tor_mtl",
                        j is not None and j["origin_city_id"] == TOR_ID and j["dest_city_id"] == MTL_ID
                        and j["departure_date"] == "2026-10-03"
                        and abs(j["price"] - CHEAPEST) < 0.011,
                       f"journey=({j['dep_time'] if j else None}, {j['price'] if j else None})")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_journeys", "basket_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
