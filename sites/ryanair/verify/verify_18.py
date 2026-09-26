#!/usr/bin/env python3
"""Verify Ryanair--18.

Log in as Carol Davis (carol.d@test.com, password TestPass123!), update her account's mobile number to +353 85 012 9999, and report how many payment methods she has saved and which card is the default. Then open her upcoming Krakow booking and report the booking reference, the fare type, the outbound flight number and departure time, her allocated outbound seat, the return departure time, and the total paid. If online check-in is open, check in and report the seat on her boarding pass. Also report the help centre fee for re-issuing a paper boarding pass.
"""
from verify_lib import (Judge, booking_by_ref, check_only_tables_changed, check_seed_rows_preserved,
                        check_signed_in_as, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_any, contains_count, contains_phrase,
                        contains_time, final_answer, payment_methods_of, run_verifier,
                        user_by_email)

TASK_ID = "Ryanair--18"
EMAIL = "carol.d@test.com"
PHONE = "+353 85 012 9999"
KRAKOW_REF = "K5R7JT"
FARE = "regular"
OUT_FLIGHT = "FR 5105"
OUT_DEP = "08:00"
SEAT = "12B"
RETURN_DEP = "13:25"
TOTAL = 136.66
REISSUE_FEE = 20.00


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_account", "/gb/en/myryanair/account")
    carol = user_by_email(after_db, EMAIL)
    judge.check("phone_matches_expected", carol is not None and carol["phone"] == PHONE,
                f"phone={carol and carol['phone']!r}, expected {PHONE!r}")
    cards = payment_methods_of(after_db, carol["id"])
    judge.check("one_saved_visa_default",
                len(cards) == 1 and cards[0]["card_type"] == "Visa"
                and cards[0]["last4"] == "1881" and cards[0]["is_default"],
                f"cards={[(c['card_type'], c['last4'], c['is_default']) for c in cards]!r}")
    judge.check("answer_reports_card_state",
                contains_count(answer, 1) and contains_any(answer, ["visa", "1881"]),
                "answer must report 1 saved method, the Visa ending 1881 (default)")
    check_visited_path(judge, traj, "visited_krakow_booking", f"/gb/en/booking/{KRAKOW_REF}")
    check_visited_path(judge, traj, "visited_checkin", f"/gb/en/check-in/{KRAKOW_REF}")
    check_visited_path(judge, traj, "visited_boarding_pass", f"/gb/en/boarding-pass/{KRAKOW_REF}")
    bk = booking_by_ref(after_db, KRAKOW_REF)
    judge.check("krakow_booking_exists", bk is not None, f"ref={KRAKOW_REF}")
    if bk:
        judge.check("krakow_checked_in", bool(bk["checked_in"]),
                    f"checked_in={bk['checked_in']!r}")
        judge.check("krakow_total", abs(bk["total"] - TOTAL) < 0.011,
                    f"total={bk['total']!r}, expected {TOTAL}")
    judge.check("answer_booking_facts",
                contains_phrase(answer, KRAKOW_REF) and contains_phrase(answer, FARE)
                and contains_phrase(answer, OUT_FLIGHT) and contains_time(answer, OUT_DEP)
                and contains_phrase(answer, SEAT) and contains_time(answer, RETURN_DEP)
                and contains_amount(answer, TOTAL),
                f"answer must report {KRAKOW_REF}, {FARE} fare, {OUT_FLIGHT} at {OUT_DEP}, "
                f"seat {SEAT}, return {RETURN_DEP}, total {TOTAL}")
    check_visited_path(judge, traj, "visited_help_checkin", "/gb/en/r/help/check-in")
    judge.check("answer_reissue_fee_20", contains_amount(answer, REISSUE_FEE),
                f"expected re-issue fee £{REISSUE_FEE:.2f}")
    check_seed_rows_preserved(judge, initial_db, after_db, "users", "id",
                              mutable_fields=("phone",))
    check_only_tables_changed(judge, initial_db, after_db, ("users", "bookings"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
