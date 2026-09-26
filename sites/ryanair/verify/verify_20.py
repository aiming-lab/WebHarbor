#!/usr/bin/env python3
"""Verify Ryanair--20.

On the Flights to Dublin page, find the fare offered from Birmingham and report the departure date and price shown. There is a newsletter welcome promo code on the homepage — find it, then book that Birmingham to Dublin flight one-way for 1 adult on the Basic fare as a guest (email tom@example.com, any valid card and address), applying the promo code. Report the discount it gave and the total paid.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, navigated_select, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--20"
PAGE_FARE = 12.49
PAGE_DATE = "2026-10-14"
PROMO = "RYANAIR10"
DISCOUNT = 0.51
FLIGHTS_TOTAL = 11.98
TOTAL = 12.22
EMAIL = "tom@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_flights_to_dublin", "/flights/gb/en/flights-to-dublin")
    judge.check("answer_page_fare_12_49", contains_amount(answer, PAGE_FARE),
                f"expected the Birmingham fare shown on the page £{PAGE_FARE:.2f}")
    judge.check("answer_page_date_14_oct",
                contains_any(answer, ["14 oct", "wed 14", "14 october", "2026-10-14"]),
                "expected the Birmingham departure date Wed 14 Oct")
    judge.check("answer_names_promo", contains_phrase(answer, PROMO),
                f"expected the promo code {PROMO!r}")
    judge.check("answer_discount_0_51",
                contains_amount(answer, DISCOUNT) or contains_phrase(answer, "10%"),
                f"expected the discount £{DISCOUNT:.2f} (10%)")
    judge.check("answer_total_12_22", contains_amount(answer, TOTAL),
                f"expected total paid £{TOTAL:.2f}")
    judge.check("visited_results_with_promo",
                navigated_select(traj, "BHX", "DUB", PAGE_DATE),
                "required: select page for BHX-DUB one-way 14 Oct")
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
        judge.check("promo_applied", (b["promo_code"] or "") == PROMO,
                    f"promo_code={b['promo_code']!r}")
        judge.check("booked_one_way_14oct_basic",
                    str(b["outbound_date"]) == PAGE_DATE and b["inbound_schedule_id"] is None
                    and b["fare_type"] == "basic" and b["adults"] == 1,
                    f"(date,inbound,fare,adults)=({b['outbound_date']},{b['inbound_schedule_id']},"
                    f"{b['fare_type']},{b['adults']})")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_bhx_dub",
                    out_s is not None and out_s["origin_code"] == "BHX"
                    and out_s["destination_code"] == "DUB",
                    f"route={out_s and (out_s['origin_code'], out_s['destination_code'])}")
        judge.check("flights_total_11_98", abs(b["flights_total"] - FLIGHTS_TOTAL) < 0.011,
                    f"flights_total={b['flights_total']!r}, expected {FLIGHTS_TOTAL}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
