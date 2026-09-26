#!/usr/bin/env python3
"""Verify Ryanair--14.

Compare the STANDARD INSURANCE and INSURANCE PLUS policies offered on the extras step of a booking. Which one offers nil-excess medical cover up to £5,000,000? Book a return trip Glasgow to Malaga, departing 12 October, returning 19 October, for 2 adults on the Basic fare, add that insurance policy, and pay as a guest (email eva@example.com, any valid card and address). Report the insurance cost and the total.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_confirmation, navigated_select, run_verifier, schedule_of)

TASK_ID = "Ryanair--14"
OUT_DATE, IN_DATE = "2026-10-12", "2026-10-19"
OUT_FLIGHT, IN_FLIGHT = "FR 4181", "FR 3021"   # 34.49 / 32.99
INSURANCE_COST = 30.40     # 1.90 x 8 days x 2 pax
FLIGHTS_TOTAL = 134.96
TOTAL = 168.67
EMAIL = "eva@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_extras_page", any("/gb/en/trip/flights/extras" in u for u in
                    [s.get("url", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "required: the extras step (insurance comparison surface)")
    judge.check("answer_names_insurance_plus",
                contains_phrase(answer, "insurance plus") or contains_phrase(answer, "ins plus"),
                "INSURANCE PLUS is the policy with nil-excess medical cover up to £5,000,000")
    judge.check("answer_insurance_cost_30_40", contains_amount(answer, INSURANCE_COST),
                f"expected insurance cost £{INSURANCE_COST:.2f}")
    judge.check("answer_total_168_67", contains_amount(answer, TOTAL),
                f"expected total £{TOTAL:.2f}")
    judge.check("visited_results_for_route_dates",
                navigated_select(traj, "GLA", "AGP", OUT_DATE, IN_DATE),
                "required: select page for GLA-AGP 12->19 Oct")
    for name, path in (("visited_seats", "/gb/en/trip/flights/seats"),
                       ("visited_bags", "/gb/en/trip/flights/bags"),
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
        judge.check("booked_basic_2pax",
                    b["fare_type"] == "basic" and b["adults"] == 2,
                    f"(fare,adults)=({b['fare_type']!r},{b['adults']})")
        judge.check("insurance_plus_on_booking", b["insurance_key"] == "plus",
                    f"insurance={b['insurance_key']!r}")
        judge.check("extras_total_30_40", abs(b["extras_total"] - INSURANCE_COST) < 0.011,
                    f"extras_total={b['extras_total']!r}, expected {INSURANCE_COST}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
