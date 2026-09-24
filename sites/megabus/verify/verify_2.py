#!/usr/bin/env python3
"""Verify Megabus--2.

Create a new megabus account (Jordan Reyes, jordan.reyes@example.com,
BookBus2026!) then book the cheapest Boston→New York bus on October 3rd for one
traveler as that account and pay; report the order reference.

Frozen ground truth (seed DB): BOS→NY 2026-10-03 cheapest = 06:00 departure @
$34.99 (06:00 and 06:30 both 34.99). Signed-in checkout: booking fee $3.99;
total = 34.99 + 3.99 = $38.98. The added user row must carry the exact first/
last name and email; the added booking is matched by email + total + journey
and the answer must quote the created reference.
"""
from verify_lib import (Judge, added_bookings, added_users, booking_journeys_of,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer, journey_of,
                        navigated_confirmation, navigated_journeys, run_verifier)

TASK_ID = "Megabus--2"
BOS_ID, NY_ID = 94, 123
CHEAPEST_FARE = 34.99
TOTAL = 38.98
EMAIL = "jordan.reyes@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_register", "/account-management/register")
    judge.check("visited_journeys_results",
                navigated_journeys(traj, BOS_ID, NY_ID, "2026-10-03"),
                "required: /journey-planner/journeys?originId=94&destinationId=123&departureDate=2026-10-03")
    check_visited_path(judge, traj, "visited_basket", "/journey-planner/basket")
    check_visited_path(judge, traj, "visited_passenger_details", "/journey-planner/passenger-details")
    check_visited_path(judge, traj, "visited_payment", "/journey-planner/payment")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /journey-planner/confirmation/<ref>")
    # DB after-state: one added user row, one added booking row (signed-in), basket consumed
    users = added_users(after_db, initial_db)
    judge.check("one_user_added", len(users) == 1, f"added_users={[u['email'] for u in users]!r}")
    if users:
        u = users[0]
        judge.check("added_user_identity",
                   (u["email"] or "").lower() == EMAIL and u["first_name"] == "Jordan"
                   and u["last_name"] == "Reyes",
                   f"user=({u['email']!r}, {u['first_name']!r}, {u['last_name']!r})")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1, f"added={[r['reference'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["email"] or "").lower() == EMAIL, f"email={b['email']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                   f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["reference"]),
                    f"answer must quote the created order reference {b['reference']!r}")
        bjs = booking_journeys_of(after_db, b["id"])
        judge.check("added_booking_journeys", len(bjs) == 1 and bjs[0]["passengers"] == 1,
                   f"booking_journeys={bjs!r}")
        if bjs:
            j = journey_of(after_db, bjs[0]["journey_id"])
            judge.check("booked_cheapest_bos_ny",
                        j is not None and j["origin_city_id"] == BOS_ID and j["dest_city_id"] == NY_ID
                        and j["departure_date"] == "2026-10-03"
                        and abs(j["price"] - CHEAPEST_FARE) < 0.011,
                       f"journey=({j['dep_time'] if j else None}, {j['price'] if j else None})")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "bookings", "booking_journeys", "basket_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
