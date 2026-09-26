#!/usr/bin/env python3
"""Verify Ryanair--17.

Using the route map, list every Greek destination Ryanair serves with its airport code. Then use the cheap flight destinations page to find the cheapest one-way Basic fare from London Stansted to any Greek destination, and book it for 1 adult as a guest (email yannis@example.com, any valid card and address) on the date shown on its card. Report the destination, its price, and the booking reference.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, run_verifier, schedule_of)

TASK_ID = "Ryanair--17"
GREEK = {"ATH": "Athens", "CFU": "Corfu", "CHQ": "Chania", "EFL": "Kefalonia",
         "JTR": "Santorini", "KGS": "Kos", "RHO": "Rhodes", "SKG": "Thessaloniki",
         "ZTH": "Zakynthos"}
CHEAPEST_CODE = "ATH"
CHEAPEST_DATE = "2026-10-15"
PRICE = 24.49
EMAIL = "yannis@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_route_map", "/gb/en/route-map")
    check_visited_path(judge, traj, "visited_fare_finder", "/gb/en/cheap-flight-destinations")
    # the answer must list all nine Greek destinations with their codes
    missing = [f"{name} ({code})" for code, name in GREEK.items()
               if not (contains_phrase(answer, code.lower()) and contains_phrase(answer, name.lower()))]
    judge.check("answer_lists_all_greek_destinations", not missing,
                f"missing from answer: {missing!r}")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_cheapest_greek_athens",
                    out_s is not None and out_s["destination_code"] == CHEAPEST_CODE,
                    f"destination={out_s and out_s['destination_code']!r}, expected {CHEAPEST_CODE}")
        judge.check("booked_card_date",
                    str(b["outbound_date"]) == CHEAPEST_DATE,
                    f"outbound_date={b['outbound_date']!r}, card date {CHEAPEST_DATE}")
        judge.check("booked_one_way_basic_1pax",
                    b["inbound_schedule_id"] is None and b["fare_type"] == "basic"
                    and b["adults"] == 1,
                    f"(inbound,fare,adults)=({b['inbound_schedule_id']},{b['fare_type']},{b['adults']})")
        judge.check("booked_at_card_price",
                    abs(b["flights_total"] - PRICE) < 0.011,
                    f"flights_total={b['flights_total']!r}, expected {PRICE}")
        judge.check("answer_names_destination_price",
                    contains_any(answer, ["athens", "ath"]) and contains_amount(answer, PRICE),
                    "answer must name Athens and its price £24.49")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
                       ("visited_extras", "/gb/en/trip/flights/extras"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
