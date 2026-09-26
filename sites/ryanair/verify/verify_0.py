#!/usr/bin/env python3
"""Verify Ryanair--0.

My partner and I want a city break in Dublin. Book the cheapest return trip from London Stansted on Tuesday 13 October, returning Tuesday 20 October, for 2 adults on the Basic fare, with no seats, no bags and no extras. Pay as a guest: email john.smith@example.com, mobile +44 7700 900123, Visa 4242 4242 4242 4242 (exp 09/29, CVV 123), billing 1 Test Street, London, E1 6AN. Report the booking reference and the total charged.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--0"
OUT_DATE, IN_DATE = "2026-10-13", "2026-10-20"
OUT_FLIGHT, IN_FLIGHT = "FR 289", "FR 202"   # cheapest on each day (17.98 / 18.49)
FLIGHTS_TOTAL = 72.94                        # (17.98 + 18.49) x 2 adults
CARD_FEE = 1.46
TOTAL = 74.40
EMAIL = "john.smith@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "DUB", OUT_DATE, IN_DATE),
                "required: /gb/en/trip/flights/select?originIata=STN&destinationIata=DUB&dateOut=2026-10-13&dateIn=2026-10-20")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
                       ("visited_extras", "/gb/en/trip/flights/extras"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    judge.check("answer_total_74_40", contains_amount(answer, TOTAL),
                f"expected charged total £{TOTAL:.2f} (flights {FLIGHTS_TOTAL} + 2% card fee {CARD_FEE})")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        judge.check("added_booking_fare_basic", b["fare_type"] == "basic", f"fare={b['fare_type']!r}")
        judge.check("added_booking_pax", b["adults"] == 2 and b["teens"] == 0
                    and b["children"] == 0, f"pax=({b['adults']},{b['teens']},{b['children']})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        in_s = schedule_of(after_db, b["inbound_schedule_id"]) if b["inbound_schedule_id"] else None
        judge.check("booked_route_STN_DUB",
                    out_s is not None and out_s["origin_code"] == "STN"
                    and out_s["destination_code"] == "DUB",
                    f"outbound={out_s and (out_s['origin_code'], out_s['destination_code'])}")
        judge.check("booked_dates",
                    str(b["outbound_date"]) == OUT_DATE and str(b["inbound_date"]) == IN_DATE,
                    f"dates=({b['outbound_date']}, {b['inbound_date']})")
        judge.check("booked_cheapest_outbound",
                    out_s is not None and out_s["flight_number"] == OUT_FLIGHT,
                    f"outbound_flight={out_s and out_s['flight_number']!r}, expected {OUT_FLIGHT}")
        judge.check("booked_cheapest_inbound",
                    in_s is not None and in_s["flight_number"] == IN_FLIGHT,
                    f"inbound_flight={in_s and in_s['flight_number']!r}, expected {IN_FLIGHT}")
        judge.check("no_seats_bags_extras",
                    abs(b["seats_total"]) < 0.01 and abs(b["bags_total"]) < 0.01
                    and abs(b["extras_total"]) < 0.01,
                    f"seats={b['seats_total']}, bags={b['bags_total']}, extras={b['extras_total']}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
        pax = passengers_of(after_db, b["id"])
        judge.check("two_passenger_rows", len(pax) == 2, f"passengers={len(pax)}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
