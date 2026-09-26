#!/usr/bin/env python3
"""Verify Ryanair--16.

I need to be in Dublin by 10am. Book the cheapest one-way morning flight (departing before 10:00) from London Stansted on 5 November for 1 adult on the Basic fare, as a guest (email nina@example.com, any valid card and address). Report the flight number, its departure time, and the total paid.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, contains_time,
                        final_answer, navigated_confirmation, navigated_select, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--16"
OUT_DATE = "2026-11-05"
OUT_FLIGHT = "FR 271"
DEP = "06:30"
FLIGHTS_TOTAL = 27.49
TOTAL = 28.04
EMAIL = "nina@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "DUB", OUT_DATE),
                "required: select page for STN-DUB on 5 Nov")
    judge.check("answer_flight_number", contains_phrase(answer, OUT_FLIGHT),
                f"expected {OUT_FLIGHT}")
    judge.check("answer_dep_time", contains_time(answer, DEP), f"expected departure {DEP}")
    judge.check("answer_total_28_04", contains_amount(answer, TOTAL),
                f"expected total £{TOTAL:.2f}")
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
        judge.check("booked_one_way_5nov_basic",
                    str(b["outbound_date"]) == OUT_DATE and b["inbound_schedule_id"] is None
                    and b["fare_type"] == "basic" and b["adults"] == 1,
                    f"(date,inbound,fare,adults)=({b['outbound_date']},{b['inbound_schedule_id']},"
                    f"{b['fare_type']},{b['adults']})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_morning_flight",
                    out_s is not None and out_s["flight_number"] == OUT_FLIGHT
                    and out_s["departure"] == DEP,
                    f"flight=({out_s and out_s['flight_number']}, {out_s and out_s['departure']})")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
