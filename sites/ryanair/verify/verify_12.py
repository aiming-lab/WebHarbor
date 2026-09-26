#!/usr/bin/env python3
"""Verify Ryanair--12.

I need to be in Marrakesh on a weekend. Use the flight timetable for London Stansted to Marrakesh: report the flight number, its departure and arrival times, and which two days of the week it does NOT operate. Then book the cheapest one-way Basic fare for the first Saturday after 10 October for 1 adult as a guest (email petra@example.com, any valid card and address), and report the price paid and the booking reference.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, contains_time,
                        final_answer, navigated_confirmation, run_verifier, schedule_of,
                        site_urls, normalized_url_path, _query_params)

TASK_ID = "Ryanair--12"
FLIGHT = "FR 1921"
DEP, ARR = "21:15", "01:27"
NON_OPERATING = ("thursday", "friday")
OUT_DATE = "2026-10-17"
FLIGHTS_TOTAL = 59.49
TOTAL = 60.68
EMAIL = "petra@example.com"


def _visited_timetable(traj):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/gb/en/trip/flights/timetable":
            continue
        q = _query_params(u)
        if "STN" in q.get("originIata", []) and "RAK" in q.get("destinationIata", []):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_timetable_stn_rak", _visited_timetable(traj),
                "required: /gb/en/trip/flights/timetable?originIata=STN&destinationIata=RAK")
    judge.check("answer_flight_number", contains_phrase(answer, FLIGHT),
                f"expected flight {FLIGHT}")
    judge.check("answer_dep_time", contains_time(answer, DEP), f"expected departure {DEP}")
    judge.check("answer_arrival_time", contains_time(answer, ARR), f"expected arrival {ARR}")
    judge.check("answer_non_operating_days",
                contains_phrase(answer, "thursday") and contains_phrase(answer, "friday"),
                "answer must name Thursday and Friday as the non-operating days")
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
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_first_saturday_17_oct",
                    str(b["outbound_date"]) == OUT_DATE and b["inbound_schedule_id"] is None,
                    f"outbound={b['outbound_date']!r}, inbound={b['inbound_schedule_id']!r}")
        judge.check("booked_fr1921", out_s is not None and out_s["flight_number"] == FLIGHT,
                    f"flight={out_s and out_s['flight_number']!r}")
        judge.check("booked_basic_1pax", b["adults"] == 1 and b["fare_type"] == "basic",
                    f"(adults,fare)=({b['adults']},{b['fare_type']!r})")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
        judge.check("answer_price_paid", contains_amount(answer, TOTAL),
                    f"expected price paid £{TOTAL:.2f}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
