#!/usr/bin/env python3
"""Verify Ryanair--4.

I'm flying London Stansted to Alicante on 15 October, returning 22 October, with a friend, on the Basic fare. Add Priority & 2 Cabin Bags for both passengers and one 20kg check-in bag for me only, on both flights. Pay as a guest (email dave@example.com, any valid card and address). Report how much the bags added compared with travelling with only the free small bags, and the final total.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, passengers_of, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--4"
OUT_DATE, IN_DATE = "2026-10-15", "2026-10-22"
OUT_FLIGHT, IN_FLIGHT = "FR 7958", "FR 1652"   # 43.49 / 26.49
FLIGHTS_TOTAL = 139.96
BAGS_TOTAL = 114.98    # 4 x 16.00 priority + 2 x 25.49 20kg
TOTAL = 260.04
EMAIL = "dave@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "STN", "ALC", OUT_DATE, IN_DATE),
                "required: select page for STN-ALC 15->22 Oct")
    check_visited_path(judge, traj, "visited_bags_page", "/gb/en/trip/flights/bags")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_extras", "/gb/en/trip/flights/extras"),
                       ("visited_payment", "/gb/en/payment")):
        check_visited_path(judge, traj, name, path)
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /gb/en/booking/confirmation/<ref>")
    judge.check("answer_bags_added_114_98", contains_amount(answer, BAGS_TOTAL),
                f"expected bags added £{BAGS_TOTAL:.2f} (4x£16.00 priority + 2x£25.49)")
    judge.check("answer_total_260_04", contains_amount(answer, TOTAL),
                f"expected final total £{TOTAL:.2f}")
    added = added_bookings(after_db, initial_db)
    judge.check("one_booking_added", len(added) == 1,
                f"added_bookings={[r['booking_ref'] for r in added]!r}")
    if added:
        b = added[0]
        judge.check("added_booking_email", (b["contact_email"] or "").lower() == EMAIL,
                    f"email={b['contact_email']!r}")
        judge.check("basic_fare", b["fare_type"] == "basic", f"fare={b['fare_type']!r}")
        judge.check("two_adults", b["adults"] == 2, f"adults={b['adults']}")
        judge.check("bags_total_114_98", abs(b["bags_total"] - BAGS_TOTAL) < 0.011,
                    f"bags_total={b['bags_total']!r}, expected {BAGS_TOTAL}")
        pax = passengers_of(after_db, b["id"])
        judge.check("priority_cabin_both_pax_both_flights",
                    len(pax) == 2 and all(p["cabin_out"] == "priority" and p["cabin_in"] == "priority"
                                          for p in pax),
                    f"cabin={[(p['cabin_out'], p['cabin_in']) for p in pax]!r}")
        judge.check("one_20kg_pax0_both_flights",
                    pax and pax[0]["checkin_20kg_out"] == 1 and pax[0]["checkin_20kg_in"] == 1
                    and pax[1]["checkin_20kg_out"] == 0 and pax[1]["checkin_20kg_in"] == 0,
                    f"20kg rows=({pax[0]['checkin_20kg_out']},{pax[0]['checkin_20kg_in']},"
                    f"{pax[1]['checkin_20kg_out']},{pax[1]['checkin_20kg_in']})")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
