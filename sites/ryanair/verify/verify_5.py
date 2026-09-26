#!/usr/bin/env python3
"""Verify Ryanair--5.

Book a return trip Birmingham to Faro, departing Saturday 10 October, returning Sunday 18 October, for 2 adults on the Plus fare. Add Security Fast Track for both passengers at both airports and the Insurance Plus policy on the extras step. Pay as a guest (email ana@example.com, any valid card and address). Report the extras total shown in the price breakdown and the booking reference.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, run_verifier, schedule_of)

TASK_ID = "Ryanair--5"
OUT_DATE, IN_DATE = "2026-10-10", "2026-10-18"
OUT_FLIGHT, IN_FLIGHT = "FR 4329", "FR 1850"   # cheapest plus legs (93.49 / 171.98)
FLIGHTS_TOTAL = 530.94
EXTRAS_TOTAL = 78.12    # fast track (BHX+FAO) x2 + Insurance Plus 9 days x2
TOTAL = 621.24
EMAIL = "ana@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "BHX", "FAO", OUT_DATE, IN_DATE),
                "required: select page for BHX-FAO 10->18 Oct")
    check_visited_path(judge, traj, "visited_extras_page", "/gb/en/trip/flights/extras")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    judge.check("answer_extras_total_78_12", contains_amount(answer, EXTRAS_TOTAL),
                f"expected extras total £{EXTRAS_TOTAL:.2f}")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        judge.check("booked_plus_fare", b["fare_type"] == "plus", f"fare={b['fare_type']!r}")
        judge.check("two_adults", b["adults"] == 2, f"adults={b['adults']}")
        judge.check("fast_track_added", bool(b["fast_track_out"]),
                    f"fast_track_out={b['fast_track_out']!r}")
        judge.check("insurance_plus_added", b["insurance_key"] == "plus",
                    f"insurance={b['insurance_key']!r}")
        judge.check("extras_total_78_12", abs(b["extras_total"] - EXTRAS_TOTAL) < 0.011,
                    f"extras_total={b['extras_total']!r}, expected {EXTRAS_TOTAL}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
