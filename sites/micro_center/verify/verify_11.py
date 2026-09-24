#!/usr/bin/env python3
"""Verify Micro Center--11.

Log in as alice.j@test.com. Add a Mastercard ending in 5678 (expiring 05/2029)
and an American Express ending in 9012 (expiring 11/2027), make the
Mastercard the default, then remove the old Mastercard. Report how many
payment methods are saved now, which one is the default, and which card was
removed.

Frozen ground truth (seed DB): alice starts with Visa 2111 (default) and
Mastercard 2777. After the task she must have exactly 3 cards — Visa 2111,
Mastercard 5678 (exp 05/2029, the default), American Express 9012 (exp
11/2027) — and the old Mastercard 2777 must be gone.
"""
from verify_lib import (check_signed_in_as, check_only_tables_changed,
                        check_trajectory_identity, contains_count, contains_phrase,
                        final_answer, navigated_to_path, payment_cards_of, run_verifier)

TASK_ID = "Micro Center--11"
EMAIL = "alice.j@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_payments_page", navigated_to_path(traj, "/account/payments"),
                "required_path=/account/payments")
    cards = payment_cards_of(after_db, EMAIL)
    judge.check("three_cards_saved", len(cards) == 3,
                f"cards={[(c['brand'], c['last4'], c['is_default']) for c in cards]!r}")
    new_mc = [c for c in cards if c["last4"] == "5678"]
    amex = [c for c in cards if c["last4"] == "9012"]
    judge.check("new_mastercard_present",
                len(new_mc) == 1 and new_mc[0]["brand"] == "Mastercard"
                and new_mc[0]["exp_month"] == "05" and new_mc[0]["exp_year"] == "2029",
                f"new_mastercard={new_mc!r}")
    judge.check("new_amex_present",
                len(amex) == 1 and amex[0]["brand"] == "American Express"
                and amex[0]["exp_month"] == "11" and amex[0]["exp_year"] == "2027",
                f"new_amex={amex!r}")
    if new_mc:
        judge.check("mastercard_is_default", new_mc[0]["is_default"] == 1,
                    f"is_default={new_mc[0]['is_default']!r}")
    others = [c for c in cards if c["last4"] not in ("5678",)]
    judge.check("no_other_default",
                all(c["is_default"] == 0 for c in others),
                f"other_defaults={[(c['last4'], c['is_default']) for c in others]!r}")
    judge.check("old_mastercard_removed",
                all(c["last4"] != "2777" for c in cards),
                "the old Mastercard 2777 must be gone")
    judge.check("answer_quotes_card_count", contains_count(answer, 3),
                "expected_count=3")
    judge.check("answer_names_default_card",
                contains_phrase(answer, "5678") and contains_phrase(answer, "mastercard"),
                "expected: Mastercard ending in 5678 is the default")
    judge.check("answer_names_removed_card",
                contains_phrase(answer, "2777"),
                "expected: the removed card is the Mastercard ending in 2777")
    check_only_tables_changed(judge, initial_db, after_db, ("payment_cards",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
