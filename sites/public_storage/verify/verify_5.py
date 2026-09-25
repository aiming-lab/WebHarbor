#!/usr/bin/env python3
"""Verify Public Storage--5 (stateful: bill pay) — r2 task text.

Log in to Pay Bill with account number 517204 and email bob.c@test.com.
Before paying, report the size of the unit being billed, its monthly rate,
the current balance due, and the facility's street address. Then pay the
full balance with Visa card 4242 4242 4242 4242 (expiring 11/28, security
code 123), and report the payment confirmation number, the amount charged,
the remaining balance, the next bill date, and the card's last four digits
shown on the receipt.

Frozen ground truth (seed DB): account 517204 is bob.c@test.com; his rental
(Medium 10'x10' at 4072 N Broadway Street, Chicago) runs $186.00/month with
a $186.00 balance due and next bill date 10/01/2026. After the task: exactly
one payment row (amount 186.00, card last4 4242, confirmation PS-PAY-xxxxxx)
and bob's rental balance drops to 0; nothing else changes.
"""
from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_amount, contains_any_phrase,
                        contains_phrase, contains_payment_code, entered_identity,
                        final_answer, navigated_bill_pay, navigated_bill_pay_login,
                        rows_of, run_verifier, user_by_email)

TASK_ID = "Public Storage--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_bill_pay_login", navigated_bill_pay_login(traj),
                "required: Pay Bill login page")
    judge.check("entered_account_number", entered_identity(traj, "517204"),
                "required: account number 517204")
    judge.check("entered_bob_email", entered_identity(traj, "bob.c@test.com"),
                "required: email bob.c@test.com")
    judge.check("visited_bill_pay", navigated_bill_pay(traj),
                "required: Pay Bill page / receipt")
    judge.check("entered_card", entered_identity(traj, "4242"),
                "required: the Visa card number")
    # answer gates — pre-payment facts
    judge.check("answer_billed_unit_size",
                contains_phrase(answer, "10'x10'") or contains_phrase(answer, "10x10")
                or contains_phrase(answer, "10 x 10"),
                "billed unit size 10'x10'")
    judge.check("answer_monthly_rate", contains_amount(answer, 186),
                "monthly rate $186.00 (also the balance due)")
    judge.check("answer_balance_due", contains_amount(answer, 186),
                "current balance due $186.00")
    judge.check("answer_facility_address", contains_phrase(answer, "4072 N Broadway Street"),
                "facility street address 4072 N Broadway Street")
    # answer gates — receipt facts
    judge.check("answer_confirmation", contains_payment_code(answer),
                "a PS-PAY-xxxxxx confirmation number")
    judge.check("answer_amount_charged", contains_amount(answer, 186),
                "amount charged $186.00")
    judge.check("answer_remaining_balance",
                contains_phrase(answer, "$0") or contains_amount(answer, 0),
                "remaining balance $0.00")
    judge.check("answer_next_bill", contains_phrase(answer, "10/01/2026"),
                "next bill date 10/01/2026")
    judge.check("answer_card_last4", contains_phrase(answer, "4242"),
                "card last four digits 4242 on the receipt")
    # DB delta: one payment row + bob's rental balance 186 -> 0
    check_only_tables_changed(judge, initial_db, after_db, {"payments", "rentals"})
    new = added_rows(after_db, initial_db, "payments", "id")
    judge.check("exactly_one_payment", len(new) == 1,
                f"payments delta = {len(new)}")
    pay = new[0] if new else {}
    bob = user_by_email(initial_db, "bob.c@test.com")
    rental = (rows_of(initial_db, "rentals", "WHERE user_id = ?", ((bob or {}).get("id"),)) or [{}])[0]
    judge.check("payment_rental", pay.get("rental_id") == rental.get("id"),
                f"rental_id={pay.get('rental_id')!r}")
    judge.check("payment_amount", abs((pay.get("amount") or 0) - 186.0) < 0.01,
                f"amount={pay.get('amount')!r}")
    judge.check("payment_last4", pay.get("card_last4") == "4242",
                f"card_last4={pay.get('card_last4')!r}")
    after_rental = (rows_of(after_db, "rentals", "WHERE id = ?", (rental.get("id"),)) or [{}])[0]
    bal = after_rental.get("balance_due")
    judge.check("rental_balance_cleared",
                bal is not None and abs(bal - 0.0) < 0.01,
                f"balance_due={bal!r}")
    judge.check("answer_confirmation_matches_db",
                contains_phrase(answer, str(pay.get("confirmation") or "###")),
                f"reported confirmation must equal the DB value {pay.get('confirmation')!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
