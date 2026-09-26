#!/usr/bin/env python3
"""Verify Ryanair--6.

I saw the newsletter welcome offer on the homepage. Book the cheapest return trip Edinburgh to Dublin, departing 20 October, returning 27 October, for 1 adult on the Basic fare, applying the newsletter promo code in the search widget. Pay as a guest (email sam@example.com, any valid card and address). Report the promo code you used, the discount it gave you, and the total paid.
"""
from verify_lib import (Judge, added_bookings, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_phrase,
                        final_answer, navigated_confirmation, navigated_select, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--6"
OUT_DATE, IN_DATE = "2026-10-20", "2026-10-27"
OUT_FLIGHT, IN_FLIGHT = "FR 8947", "FR 7472"   # promo prices 15.49 / 13.49
PROMO = "RYANAIR10"
PROMO_PCT = 10
FLIGHTS_TOTAL = 28.98
DISCOUNT = 4.98
TOTAL = 29.56
EMAIL = "sam@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_home_for_promo", navigated_select(traj, "EDI", "DUB", OUT_DATE, IN_DATE)
                or any("promoCode" in u for u in
                       [s.get("url", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "required: search with the promo code applied")
    judge.check("answer_names_promo_code", contains_phrase(answer, PROMO),
                f"expected promo code {PROMO!r}")
    judge.check("answer_states_discount",
                contains_amount(answer, DISCOUNT) or contains_phrase(answer, "10%")
                or contains_phrase(answer, "10 percent"),
                f"expected the discount (£{DISCOUNT:.2f} / 10%)")
    judge.check("answer_total_29_56", contains_amount(answer, TOTAL),
                f"expected total paid £{TOTAL:.2f}")
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
        judge.check("promo_applied_to_booking", (b["promo_code"] or "") == PROMO,
                    f"promo_code={b['promo_code']!r}")
        judge.check("flights_total_with_promo", abs(b["flights_total"] - FLIGHTS_TOTAL) < 0.011,
                    f"flights_total={b['flights_total']!r}, expected {FLIGHTS_TOTAL}")
        judge.check("added_booking_total", abs(b["total"] - TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {TOTAL}")
        judge.check("answer_names_added_booking", contains_phrase(answer, b["booking_ref"]),
                    f"answer must quote the booking reference {b['booking_ref']!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("bookings", "booking_passengers", "trip_states"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
