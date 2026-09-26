#!/usr/bin/env python3
"""Verify Ryanair--13.

Before booking, check the help centre for the 20kg check-in bag price online versus at the airport. Then book a one-way flight London Stansted to Dublin on 14 October for 1 adult on the Basic fare, adding one 20kg check-in bag, and pay as a guest (email kim@example.com, any valid card and address). Report the bag price the site charged you and how much you saved versus the airport price.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--13"
OUT_DATE = "2026-10-14"
OUT_FLIGHT = "FR 291"          # cheapest basic leg that day (18.98)
BAG_ONLINE = 25.49
BAG_AIRPORT = 50.00
SAVED = 24.51
FLIGHTS_TOTAL = 18.98
TOTAL = 45.36
EMAIL = "kim@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_help_first",
                any("/gb/en/r/help/checkin-bags" in u or "/gb/en/r/help/fees" in u
                    for u in [s.get("url", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "required: the help centre bag-price article opened before booking")
    judge.check("answer_bag_charged_25_49", contains_amount(answer, BAG_ONLINE),
                f"expected the site to charge £{BAG_ONLINE:.2f} for the 20kg bag")
    judge.check("answer_saved_24_51", contains_amount(answer, SAVED),
                f"expected saving versus airport £{SAVED:.2f}")
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "DUB", OUT_DATE, one_way=True),
                "required: select page for STN-DUB one-way 14 Oct")
    check_visited_path(judge, traj, "visited_bags_page", "/gb/en/trip/flights/bags")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
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
        judge.check("booked_one_way_14_oct_basic",
                    str(b["outbound_date"]) == OUT_DATE and b["inbound_schedule_id"] is None
                    and b["fare_type"] == "basic" and b["adults"] == 1,
                    f"(date,inbound,fare,adults)=({b['outbound_date']},{b['inbound_schedule_id']},"
                    f"{b['fare_type']},{b['adults']})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_cheapest_flight",
                    out_s is not None and out_s["flight_number"] == OUT_FLIGHT,
                    f"flight={out_s and out_s['flight_number']!r}")
        pax = passengers_of(after_db, b["id"])
        judge.check("one_20kg_bag_added",
                    len(pax) == 1 and pax[0]["checkin_20kg_out"] == 1,
                    f"20kg_out={pax[0]['checkin_20kg_out'] if pax else None}")
        judge.check("bags_total_25_49", abs(b["bags_total"] - BAG_ONLINE) < 0.011,
                    f"bags_total={b['bags_total']!r}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
