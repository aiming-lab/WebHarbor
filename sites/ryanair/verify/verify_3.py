#!/usr/bin/env python3
"""Verify Ryanair--3.

Book a return trip for me and my daughter from Manchester to Dublin, departing 6 October, returning 10 October, on the Plus fare. I want a window seat in the extra-legroom front row (row 1) on the outbound, and the cheapest two seats together on the return. Pay as a guest: email mary@example.com, card 5555 5555 5555 4444, any valid expiry and address. Report the booking reference and how much the seats added to the total.
"""
import re
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of, seat_rows)

TASK_ID = "Ryanair--3"
OUT_DATE, IN_DATE = "2026-10-06", "2026-10-10"
EMAIL = "mary@example.com"
WINDOW_ROW1 = ("1A", "1F")
CHEAP_SEAT_PRICE = 9.50


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "MAN", "DUB", OUT_DATE, IN_DATE),
                "required: select page for MAN-DUB 6->10 Oct")
    check_visited_path(judge, traj, "visited_seats_page", "/gb/en/trip/flights/seats")
    for name, path in (("visited_bags", "/gb/en/trip/flights/bags"),
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
        judge.check("booked_plus_fare", b["fare_type"] == "plus", f"fare={b['fare_type']!r}")
        judge.check("two_adults", b["adults"] == 2, f"adults={b['adults']}")
        judge.check("booked_dates", str(b["outbound_date"]) == OUT_DATE
                    and str(b["inbound_date"]) == IN_DATE,
                    f"dates=({b['outbound_date']}, {b['inbound_date']})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        in_s = schedule_of(after_db, b["inbound_schedule_id"])
        judge.check("booked_man_dub_route",
                    out_s is not None and out_s["origin_code"] == "MAN"
                    and out_s["destination_code"] == "DUB"
                    and in_s is not None and in_s["origin_code"] == "DUB"
                    and in_s["destination_code"] == "MAN",
                    f"route=({out_s and out_s['origin_code']}->{out_s and out_s['destination_code']}, "
                    f"{in_s and in_s['origin_code']}->{in_s and in_s['destination_code']})")
        pax = passengers_of(after_db, b["id"])
        judge.check("two_passenger_rows", len(pax) == 2, f"passengers={len(pax)}")
        out_seats = [p["seat_out"] for p in pax if p["seat_out"]]
        in_seats = [p["seat_in"] for p in pax if p["seat_in"]]
        # task: a window seat in the extra-legroom front row (row 1) on the
        # outbound (the second passenger's outbound seat is the agent's choice;
        # the seats form requires every passenger to be seated on both flights)
        judge.check("outbound_row1_window",
                    len(out_seats) == 2 and any(s in WINDOW_ROW1 for s in out_seats),
                    f"outbound seats={out_seats!r}, expected one of {WINDOW_ROW1} among them")
        judge.check("return_two_cheapest_together",
                    len(in_seats) == 2 and all(re.match(r"(\d+)([A-F])", s) for s in in_seats)
                    and len({re.match(r"(\d+)", s).group(1) for s in in_seats}) == 1
                    and all(int(re.match(r"(\d+)", s).group(1)) >= 18 for s in in_seats)
                    and abs(ord(in_seats[0][-1]) - ord(in_seats[1][-1])) == 1,
                    f"return seats={in_seats!r}, expected two adjacent row>=18 seats")
        def _price(seat):
            row = int(re.match(r"(\d+)", seat).group(1))
            if row <= 2: return 21.50
            if row <= 6: return 14.00
            if row <= 15: return round(13.50 - (row - 7) * 0.50, 2)
            if row <= 17: return 14.50
            return 9.50
        expected_seats_total = round(sum(_price(s) for s in out_seats + in_seats), 2)
        judge.check("seats_total_matches_selection",
                   abs(b["seats_total"] - expected_seats_total) < 0.011,
                   f"seats_total={b['seats_total']!r}, expected {expected_seats_total}")
        expected_total = round(b["flights_total"] + expected_seats_total, 2)
        expected_total = round(expected_total + expected_total * 0.02, 2)
        judge.check("added_booking_total", abs(b["total"] - expected_total) < 0.011,
                    f"total={b['total']!r}, expected {expected_total}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
        judge.check("answer_reports_seats_added",
                    contains_amount(answer, expected_seats_total),
                    f"answer must state how much the seats added (£{expected_seats_total:.2f})")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
