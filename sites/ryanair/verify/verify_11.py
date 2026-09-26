#!/usr/bin/env python3
"""Verify Ryanair--11.

Log in as Bob Chen (bob.c@test.com, password TestPass123!). First check his account and report how many payment methods are saved and which card is the default. Then open his Dublin weekend departing in two days and report which fare it is booked on; try to check in online and report exactly when online check-in opens for his booking and why. Also find the airport fee if he never checks in online, the 20kg check-in bag price at the airport versus online, and what time the boarding gate closes.
"""
from verify_lib import (Judge, booking_by_ref, check_read_only, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_any, contains_count, contains_phrase, final_answer,
                        payment_methods_of, run_verifier)

TASK_ID = "Ryanair--11"
EMAIL = "bob.c@test.com"
REF = "M9D2XV"
FARE = "basic"
AIRPORT_CHECKIN_FEE = 55.00
BAG_AIRPORT = 50.00
BAG_ONLINE = 25.49


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_account", "/gb/en/myryanair/account")
    bob = db_user(after_db, EMAIL)
    cards = payment_methods_of(after_db, bob["id"])
    judge.check("one_saved_mastercard_default",
                len(cards) == 1 and cards[0]["card_type"] == "Mastercard"
                and cards[0]["last4"] == "5309" and cards[0]["is_default"],
                f"cards={[(c['card_type'], c['last4'], c['is_default']) for c in cards]!r}")
    judge.check("answer_reports_card_state",
                contains_count(answer, 1) and contains_any(answer, ["mastercard", "5309"]),
                "answer must report 1 saved method, the Mastercard ending 5309 (default)")
    check_visited_path(judge, traj, "visited_booking_detail", f"/gb/en/booking/{REF}")
    check_visited_path(judge, traj, "visited_checkin_page", f"/gb/en/check-in/{REF}")
    bk = booking_by_ref(after_db, REF)
    judge.check("booking_untouched", bk is not None and not bk["checked_in"]
                and bk["fare_type"] == FARE,
                f"booking=({bk and bk['checked_in']}, {bk and bk['fare_type']!r})")
    judge.check("answer_fare_basic", contains_phrase(answer, "basic"),
                "answer must report the booking is on the Basic fare")
    judge.check("answer_checkin_opens_24h",
                contains_phrase(answer, "24 hours") or contains_phrase(answer, "24 hour"),
                "answer must state online check-in opens 24 hours before departure")
    judge.check("answer_why_random",
                contains_phrase(answer, "random") or contains_phrase(answer, "allocated"),
                "answer must explain why: randomly allocated seats (no seats purchased)")
    check_visited_path(judge, traj, "visited_help_fees", "/gb/en/r/help/fees")
    judge.check("answer_airport_checkin_fee_55", contains_amount(answer, AIRPORT_CHECKIN_FEE),
                f"expected airport check-in fee £{AIRPORT_CHECKIN_FEE:.2f}")
    judge.check("answer_bag_prices",
                contains_amount(answer, BAG_AIRPORT) and contains_amount(answer, BAG_ONLINE),
                f"expected 20kg bag £{BAG_AIRPORT:.2f} airport vs £{BAG_ONLINE:.2f} online")
    judge.check("answer_gate_closes_30min",
                contains_phrase(answer, "30 min") or contains_phrase(answer, "30 minutes"),
                "answer must state the boarding gate closes 30 minutes before departure")
    check_read_only(judge, initial_db, after_db)


def db_user(db_path, email):
    from verify_lib import user_by_email
    return user_by_email(db_path, email)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
