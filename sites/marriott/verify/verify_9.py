#!/usr/bin/env python3
"""Sign in as carol.d@test.com (password TestPass123!). Replace my old Amex payment method with Visa 4242424242424444, cardholder Carol Davis, expiring 09/2029. Confirm the old card is removed and tell me which card remains, including its last four digits and expiration date."""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_amount,
                        contains_phrase, final_answer, payments_of, run_verifier,
                        table_delta, user_by_email)

TASK_ID = "Marriott--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_payments_page", "/loyalty/myAccount/paymentMethods.mi")
    # answer: one card remains (the Visa ending 4444) + profile success message
    judge.check("answer_remaining_card_last4", contains_phrase(answer, "4444"),
                "expected the remaining Visa's last four digits 4444")
    # DB after-state: payment_methods = -Amex 3007 +Visa 4444; users = carol phone
    cards = payments_of(after_db, "carol.d@test.com")
    judge.check("one_visa_4444_remains",
                len(cards) == 1 and cards[0]["card_type"] == "Visa"
                and cards[0]["last_four"] == "4444" and cards[0]["holder_name"] == "Carol Davis"
                and cards[0]["exp_month"] == 9 and cards[0]["exp_year"] == 2029,
                f"expected exactly one card: Visa 4444 Carol Davis 09/2029; observed={cards!r}")
    pm_delta = table_delta(initial_db, after_db, "payment_methods")
    judge.check("card_swap_delta",
                len(pm_delta["added"]) == 1 and len(pm_delta["removed"]) == 1
                and pm_delta["removed"][0][2:4] == ("Amex", "3007"),
                f"expected -Amex 3007 +Visa 4444; delta={pm_delta!r}")
    carol = user_by_email(after_db, "carol.d@test.com")
    check_only_tables_changed(judge, initial_db, after_db, ("payment_methods",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
