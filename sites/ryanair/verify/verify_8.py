#!/usr/bin/env python3
"""Verify Ryanair--8.

Log in as Alice Johnson (alice.j@test.com, password TestPass123!). Update her mobile number to +44 7700 900777 and her address to 2 Test Lane, Manchester, M1 1AA, and tick the newsletter deals preference. Replace her saved card: add a Mastercard ending 4444 (number 5555 5555 5555 4444, name Alice Johnson, expiry 05/28), remove the old Visa, and report how many payment methods are saved and which is the default. Finally open her upcoming Malaga booking, report its reference and total, check in online for it and report the boarding pass seat, then log out.
"""
from verify_lib import (Judge, booking_by_ref, check_only_tables_changed,
                        check_seed_rows_preserved, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count,
                        contains_phrase, db_query, final_answer, navigated_to_path,
                        payment_methods_of, run_verifier, user_by_email)

TASK_ID = "Ryanair--8"
EMAIL = "alice.j@test.com"
PHONE = "+44 7700 900777"
ADDRESS = "2 Test Lane"
CITY = "Manchester"
POSTCODE = "M1 1AA"
MALAGA_REF = "T7W3ND"
MALAGA_TOTAL = 311.07
BP_SEAT = "2C"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_account", "/gb/en/myryanair/account")
    # profile updates
    alice = user_by_email(after_db, EMAIL)
    judge.check("phone_updated", alice is not None and alice["phone"] == PHONE,
                f"phone={alice and alice['phone']!r}, expected {PHONE!r}")
    judge.check("address_updated",
                alice is not None and alice["address_line1"] == ADDRESS
                and alice["city"] == CITY and alice["postcode"] == POSTCODE,
                f"address=({alice and alice['address_line1']!r}, {alice and alice['city']!r}, "
                f"{alice and alice['postcode']!r})")
    judge.check("newsletter_ticked", alice is not None and bool(alice["newsletter"]),
                f"newsletter={alice and alice['newsletter']!r}")
    # card swap: exactly one card left, the Mastercard 4444
    cards = payment_methods_of(after_db, alice["id"])
    judge.check("one_saved_card_mastercard_4444",
                len(cards) == 1 and cards[0]["card_type"] == "Mastercard"
                and cards[0]["last4"] == "4444",
                f"cards={[(c['card_type'], c['last4']) for c in cards]!r}")
    judge.check("answer_reports_card_state",
                contains_count(answer, 1) and contains_any(answer, ["mastercard", "4444"]),
                "answer must report 1 saved payment method, the Mastercard ending 4444")
    # Malaga booking detail + online check-in
    bk = booking_by_ref(after_db, MALAGA_REF)
    judge.check("malaga_booking_exists", bk is not None, f"ref={MALAGA_REF}")
    if bk:
        judge.check("malaga_total_311_07", abs(bk["total"] - MALAGA_TOTAL) < 0.011,
                    f"total={bk['total']!r}, expected {MALAGA_TOTAL}")
        judge.check("malaga_checked_in", bool(bk["checked_in"]),
                    f"checked_in={bk['checked_in']!r}")
    check_visited_path(judge, traj, "visited_malaga_booking", f"/gb/en/booking/{MALAGA_REF}")
    check_visited_path(judge, traj, "visited_checkin", f"/gb/en/check-in/{MALAGA_REF}")
    check_visited_path(judge, traj, "visited_boarding_pass", f"/gb/en/boarding-pass/{MALAGA_REF}")
    judge.check("answer_reports_malaga_facts",
                contains_phrase(answer, MALAGA_REF) and contains_amount(answer, MALAGA_TOTAL)
                and contains_phrase(answer, BP_SEAT),
                f"answer must report reference {MALAGA_REF}, total {MALAGA_TOTAL} and seat {BP_SEAT}")
    logged_out = (navigated_to_path(traj, "/gb/en/myryanair/logout")
                  or any("logout" in str(s.get("thought", "")).lower().replace("log out", "logout")
                         or "logout" in str((s.get("params") or {}).get("selector", "")).lower().replace("log out", "logout")
                         for s in traj.get("steps", []) if isinstance(s, dict)))
    judge.check("logged_out", logged_out,
                "required: the logout action (link /gb/en/myryanair/logout)")
    # other users untouched; only alice's row may change
    check_seed_rows_preserved(judge, initial_db, after_db, "users", "id",
                              mutable_fields=("phone", "address_line1", "address_line2",
                                              "city", "postcode", "newsletter"))
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "payment_methods", "bookings"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
