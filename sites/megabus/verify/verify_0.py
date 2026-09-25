#!/usr/bin/env python3
"""Verify Megabus--0.

My cousin and I want to spend October 3rd in New York. Book us the cheapest morning bus from Baltimore to New York that day for two travelers, as a guest checkout with the email cousins.trip@example.com. Before paying, find the promotion code currently advertised on the fare finder page and apply it in the basket. Pay with any valid card and report the order reference and the total you were charged.
"""
from verify_lib import (Judge, added_bookings, booking_journeys_of, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, final_answer, journey_of, navigated_confirmation,
                        navigated_journeys, navigated_to_path, run_verifier)

TASK_ID = "Megabus--0"
BAL_ID, NY_ID = 143, 123
CHEAPEST_MORNING_FARE = 43.99
TOTAL = 86.97


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: planner results for the route+date, fare finder (promo
    # discovery), basket with the promo, guest checkout chain, confirmation
    judge.check("visited_journeys_results",
                navigated_journeys(traj, BAL_ID, NY_ID, "2026-10-03"),
                "required: /journey-planner/journeys?originId=143&destinationId=123&departureDate=2026-10-03")
    check_visited_path(judge, traj, "visited_fare_finder", "/fare-finder")
    check_visited_path(judge, traj, "visited_basket", "/journey-planner/basket")
    check_visited_path(judge, traj, "visited_passenger_details", "/journey-planner/passenger-details")
    check_visited_path(judge, traj, "visited_payment", "/journey-planner/payment")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /journey-planner/confirmation/<ref>")
    # answer: order reference + the charged total
    judge.check("answer_total_86_97", contains_amount(answer, TOTAL),
                f"expected charged total ${TOTAL:.2f} (2×43.99 − 5.00 EMAIL5 + 3.99 fee)")
    # DB after-state: exactly one booking added for the guest email with the
    # task's math; its journeys are the cheapest-morning service ×2; basket
    # consumed; nothing else changed
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1, f"added_bookings={[r['reference'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["email"] or "").lower() == "cousins.trip@example.com",
                    f"email={b['email']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                   f"total={b['total']!r}, expected {TOTAL}")
        judge.check("added_booking_confirmed", b["status"] == "confirmed", f"status={b['status']!r}")
        judge.check("answer_names_added_booking",
                    contains_phrase(answer, b["reference"]),
                    f"answer must quote the order reference {b['reference']!r} that was created")
        bjs = booking_journeys_of(after_db, b["id"])
        judge.check("added_booking_journeys", len(bjs) == 1 and bjs[0]["passengers"] == 2,
                   f"booking_journeys={bjs!r}")
        if bjs:
            j = journey_of(after_db, bjs[0]["journey_id"])
            judge.check("booked_cheapest_morning_service",
                        j is not None and j["origin_city_id"] == BAL_ID and j["dest_city_id"] == NY_ID
                        and j["departure_date"] == "2026-10-03"
                        and abs(j["price"] - CHEAPEST_MORNING_FARE) < 0.011
                        and "06:00" <= j["dep_time"] < "12:00",
                       f"journey=({j['dep_time'] if j else None}, {j['price'] if j else None})")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_journeys", "basket_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
