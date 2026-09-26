#!/usr/bin/env python3
"""Verify Ryanair--2.

My wife and I are flying London Gatwick to Malaga, departing Friday 9 October and returning Friday 16 October. Select the cheapest outbound and return flights, compare the Plus and Flexi Plus bundles, and report how much more Flexi Plus costs per person for the whole trip and which bundle allows flight changes with no fees. Book the Plus fare for us both as a guest (email sally@example.com, any valid card and address) and report the booking reference and total.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, navigated_select, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--2"
OUT_DATE, IN_DATE = "2026-10-09", "2026-10-16"
OUT_FLIGHT, IN_FLIGHT = "FR 8068", "FR 3168"   # cheapest plus legs (113.49 / 103.49)
FLEXI_DELTA = 386.00                            # flexi_plus minus plus, per person, round trip
FLIGHTS_TOTAL = 433.96
TOTAL = 442.64
EMAIL = "sally@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "LGW", "AGP", OUT_DATE, IN_DATE),
                "required: select page for LGW-AGP 9->16 Oct")
    judge.check("answer_flexi_delta_386", contains_amount(answer, FLEXI_DELTA),
                f"expected £{FLEXI_DELTA:.2f} more per person for the whole trip")
    judge.check("answer_bundle_no_fee_changes",
                contains_any(answer, ["flexi plus", "flexi_plus", "flexiplus"]),
                "Flexi Plus is the bundle allowing flight changes with no fees")
    judge.check("answer_total_442_64", contains_amount(answer, TOTAL),
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
        judge.check("booked_plus_fare", b["fare_type"] == "plus", f"fare={b['fare_type']!r}")
        judge.check("two_adults", b["adults"] == 2, f"adults={b['adults']}")
        judge.check("booked_dates", str(b["outbound_date"]) == OUT_DATE
                    and str(b["inbound_date"]) == IN_DATE,
                    f"dates=({b['outbound_date']}, {b['inbound_date']})")
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
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
