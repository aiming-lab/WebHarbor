#!/usr/bin/env python3
"""Verify Ryanair--1.

I can be flexible around mid-October. Search London Stansted to Dublin departing 13 October, returning 20 October, and use the date strips to find the cheapest displayed departure day and the cheapest displayed return day. Book the cheapest return trip for 1 adult on the Basic fare as a guest (email flexible@example.com, any valid card and address). Report the two dates you picked and the total paid.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, navigated_select, passengers_of,
                        run_verifier, schedule_of)

TASK_ID = "Ryanair--1"
OUT_DATE, IN_DATE = "2026-10-13", "2026-10-21"
OUT_FLIGHT, IN_FLIGHT = "FR 289", "FR 204"   # 17.98 / 14.99 (strip-cheapest days)
FLIGHTS_TOTAL = 32.97
TOTAL = 33.63
EMAIL = "flexible@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "DUB", "2026-10-13"),
                "required: select page for STN-DUB departing 13 Oct (strips read from here)")
    judge.check("answer_names_out_day_13",
                contains_any(answer, ["13 oct", "tuesday 13", "13 october"]),
                "the cheapest displayed departure day is Tuesday 13 October")
    judge.check("answer_names_return_day_21",
                contains_any(answer, ["21 oct", "wednesday 21", "21 october"]),
                "the cheapest displayed return day is Wednesday 21 October")
    judge.check("answer_out_price_17_98", contains_amount(answer, 17.98),
                "expected £17.98 for the outbound day")
    judge.check("answer_return_price_14_99", contains_amount(answer, 14.99),
                "expected £14.99 for the return day")
    judge.check("answer_total_33_63", contains_amount(answer, TOTAL),
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
        judge.check("booked_dates_strip_cheapest",
                    str(b["outbound_date"]) == OUT_DATE and str(b["inbound_date"]) == IN_DATE,
                    f"dates=({b['outbound_date']}, {b['inbound_date']}), expected ({OUT_DATE}, {IN_DATE})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        in_s = schedule_of(after_db, b["inbound_schedule_id"])
        judge.check("booked_cheapest_outbound",
                    out_s is not None and out_s["flight_number"] == OUT_FLIGHT,
                    f"outbound={out_s and out_s['flight_number']!r}")
        judge.check("booked_cheapest_inbound",
                    in_s is not None and in_s["flight_number"] == IN_FLIGHT,
                    f"inbound={in_s and in_s['flight_number']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
        judge.check("one_adult", b["adults"] == 1, f"adults={b['adults']}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
