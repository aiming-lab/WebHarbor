#!/usr/bin/env python3
"""Verify Ryanair--15.

Book a return trip Bristol to Barcelona for me, my wife and our teenage daughter (2 adults + 1 teen), departing 9 October, returning 16 October, on the Regular fare, with no extras. Pay as a guest (email omar@example.com, any valid card and address). Report the total, the booking reference, and what cabin bag allowance the Regular fare includes.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--15"
OUT_DATE, IN_DATE = "2026-10-09", "2026-10-16"
OUT_FLIGHT, IN_FLIGHT = "FR 6228", "FR 2870"   # regular legs 41.49 / 44.99
FLIGHTS_TOTAL = 259.44    # (41.49 + 44.99) x 3 pax
TOTAL = 264.63
EMAIL = "omar@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "BRS", "BCN", OUT_DATE, IN_DATE),
                "required: select page for BRS-BCN 9->16 Oct")
    judge.check("answer_total_264_63", contains_amount(answer, TOTAL),
                f"expected total £{TOTAL:.2f}")
    judge.check("answer_cabin_allowance_10kg",
                contains_phrase(answer, "10kg") and contains_phrase(answer, "locker"),
                "answer must state the Regular fare includes a 10kg overhead locker bag")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
                       ("visited_extras", "/gb/en/trip/flights/extras"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        judge.check("booked_regular_2a_1t",
                    b["fare_type"] == "regular" and b["adults"] == 2 and b["teens"] == 1,
                    f"(fare,adults,teens)=({b['fare_type']!r},{b['adults']},{b['teens']})")
        pax = passengers_of(after_db, b["id"])
        judge.check("three_passenger_rows", len(pax) == 3, f"passengers={len(pax)}")
        judge.check("no_extras", abs(b["seats_total"]) < 0.01 and abs(b["bags_total"]) < 0.01
                    and abs(b["extras_total"]) < 0.01,
                    f"(seats,bags,extras)=({b['seats_total']},{b['bags_total']},{b['extras_total']})")
        judge.check("flights_total_259_44", abs(b["flights_total"] - FLIGHTS_TOTAL) < 0.011,
                    f"flights_total={b['flights_total']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
