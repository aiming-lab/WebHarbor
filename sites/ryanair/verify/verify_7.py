#!/usr/bin/env python3
"""Verify Ryanair--7.

I have £25 and a free weekend. From London Stansted, use the cheap flight destinations page with a maximum price filter of £25 and a maximum duration filter of 2 hours to find the cheapest destination, then book that flight one-way on the date shown on its card, for 1 adult, Basic fare, as a guest (email leo@example.com, any valid card and address). Report the destination, its price, and the booking reference.

Note: with the £25 / 120-minute filters the two cheapest cards tie at £10.49 (Paris
Bevais BVA and Frankfurt Hahn HHN, both non-stop <= 2h). The verifier accepts either
tied destination; the price and the on-card date must match the booked leg.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, run_verifier, schedule_of, site_urls,
                        normalized_url_path, _query_params)

TASK_ID = "Ryanair--7"
PRICE = 10.49
DATE = "2026-10-21"
TIED = {"BVA": ("Paris Beauvais", DATE), "HHN": ("Frankfurt Hahn", "2026-10-14")}
EMAIL = "leo@example.com"


def _visited_fare_finder_filtered(traj, max_price, max_duration):
    for u in site_urls(traj):
        if normalized_url_path(u) != "/gb/en/cheap-flight-destinations":
            continue
        q = _query_params(u)
        if (str(max_price) in [x for v in q.get("maxPrice", []) for x in [v]]
                and str(max_duration) in q.get("maxDuration", [])):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_fare_finder_filtered",
                _visited_fare_finder_filtered(traj, 25, 120),
                "required: /gb/en/cheap-flight-destinations?...maxPrice=25&maxDuration=120")
    judge.check("answer_states_price_10_49", contains_amount(answer, PRICE),
                f"expected the cheapest card price £{PRICE:.2f}")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        out_s = schedule_of(after_db, b["outbound_schedule_id"])
        judge.check("booked_tied_cheapest_destination",
                    out_s is not None and out_s["destination_code"] in TIED,
                    f"destination={out_s and out_s['destination_code']!r}, expected one of {sorted(TIED)}")
        if out_s:
            code = out_s["destination_code"]
            expect_date = TIED[code][1]
            judge.check("booked_card_date",
                        str(b["outbound_date"]) == expect_date,
                        f"outbound_date={b['outbound_date']!r}, card date {expect_date}")
            judge.check("answer_names_destination",
                        contains_any(answer, [TIED[code][0].lower(), code.lower()]),
                        f"answer must name {TIED[code][0]} ({code})")
            judge.check("one_way_basic_1pax",
                        b["adults"] == 1 and b["fare_type"] == "basic"
                        and b["inbound_schedule_id"] is None,
                        f"(adults,fare,inbound)=({b['adults']},{b['fare_type']},{b['inbound_schedule_id']})")
            judge.check("booked_at_card_price",
                        abs(b["flights_total"] - PRICE) < 0.011,
                        f"flights_total={b['flights_total']!r}, expected {PRICE}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
                       ("visited_extras", "/gb/en/trip/flights/extras"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
