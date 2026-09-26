#!/usr/bin/env python3
"""Verify Ryanair--19.

It's my parents' golden anniversary. Book a return trip London Stansted to Palma de Mallorca, departing 20 October, returning 27 October, 2 adults, on the Plus fare: seats together in the best-value front section on both flights, one 20kg check-in bag each, Security Fast Track at Stansted, and the standard insurance policy. Pay as a guest (email grace@example.com, card 4242 4242 4242 4242, any valid expiry and address). Report the booking reference and the full price breakdown.
"""
import re
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--19"
OUT_DATE, IN_DATE = "2026-10-20", "2026-10-27"
FLIGHTS_TOTAL = 396.96
BAGS_TOTAL = 101.96          # 2 pax x 25.49 x 2 flights
FAST_TRACK = 16.98           # 8.49 x 2 pax (STN)
INSURANCE = 23.36            # 1.46 x 8 days x 2 pax
EMAIL = "grace@example.com"


def _seat_price(row):
    return {7: 13.50, 8: 13.00, 9: 12.50, 10: 12.00, 11: 11.50, 12: 11.00,
            13: 10.50, 14: 10.00, 15: 9.50}.get(row)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "PMI", OUT_DATE, IN_DATE),
                "required: select page for STN-PMI 20->27 Oct")
    check_visited_path(judge, traj, "visited_seats_page", "/gb/en/trip/flights/seats")
    check_visited_path(judge, traj, "visited_bags_page", "/gb/en/trip/flights/bags")
    check_visited_path(judge, traj, "visited_extras_page", "/gb/en/trip/flights/extras")
    check_visited_path(judge, traj, "visited_payment", "/gb/en/payment")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        judge.check("booked_plus_2pax",
                    b["fare_type"] == "plus" and b["adults"] == 2,
                    f"(fare,adults)=({b['fare_type']!r},{b['adults']})")
        judge.check("booked_dates", str(b["outbound_date"]) == OUT_DATE
                    and str(b["inbound_date"]) == IN_DATE,
                    f"dates=({b['outbound_date']}, {b['inbound_date']})")
        pax = passengers_of(after_db, b["id"])
        judge.check("two_passenger_rows", len(pax) == 2, f"passengers={len(pax)}")
        # seats together in the best-value front section (rows 7-15) on both flights
        out_seats = [p["seat_out"] for p in pax if p["seat_out"]]
        in_seats = [p["seat_in"] for p in pax if p["seat_in"]]
        for label, seats in (("outbound", out_seats), ("return", in_seats)):
            ok = (len(seats) == 2
                  and all(re.fullmatch(r"(\d+)([A-F])", s) for s in seats)
                  and all(7 <= int(re.match(r"(\d+)", s).group(1)) <= 15 for s in seats)
                  and len({re.match(r"(\d+)", s).group(1) for s in seats}) == 1
                  and abs(ord(seats[0][-1]) - ord(seats[1][-1])) == 1)
            judge.check(f"seats_together_front_{label}", ok,
                        f"{label} seats={seats!r}, expected two adjacent seats in rows 7-15")
        expected_seats = round(sum(_seat_price(int(re.match(r"(\d+)", s).group(1)))
                                   for s in out_seats + in_seats), 2)
        judge.check("seats_total_matches_selection",
                   abs(b["seats_total"] - expected_seats) < 0.011,
                   f"seats_total={b['seats_total']!r}, expected {expected_seats}")
        judge.check("bags_20kg_each_both_flights",
                    abs(b["bags_total"] - BAGS_TOTAL) < 0.011
                    and all(p["checkin_20kg_out"] == 1 and p["checkin_20kg_in"] == 1 for p in pax),
                    f"bags_total={b['bags_total']!r}, 20kg rows="
                    f"{[(p['checkin_20kg_out'], p['checkin_20kg_in']) for p in pax]!r}")
        judge.check("fast_track_stansted", bool(b["fast_track_out"]),
                    f"fast_track_out={b['fast_track_out']!r}")
        judge.check("standard_insurance", b["insurance_key"] == "standard",
                    f"insurance={b['insurance_key']!r}")
        expected_extras = round(FAST_TRACK + INSURANCE, 2)
        judge.check("extras_total", abs(b["extras_total"] - expected_extras) < 0.011,
                    f"extras_total={b['extras_total']!r}, expected {expected_extras}")
        expected_total = round(FLIGHTS_TOTAL + expected_seats + BAGS_TOTAL + expected_extras, 2)
        expected_total = round(expected_total + expected_total * 0.02, 2)
        judge.check("added_booking_total", abs(b["total"] - expected_total) < 0.011,
                    f"total={b['total']!r}, expected {expected_total}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
        judge.check("answer_reports_breakdown_total",
                    contains_amount(answer, expected_total),
                    f"answer must report the full-breakdown total £{expected_total:.2f}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
