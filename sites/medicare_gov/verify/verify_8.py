#!/usr/bin/env python3
"""Verify Medicare.gov--8 — Bob's fraud check + premium payment + address change.

Stateful task (two state changes + login). Ground truth (frozen seed): the
I-MEDIC fraud line for Medicare Advantage / drug plan fraud is 1-877-7SAFERX
(1-877-772-3379); Bob's due Part B premium ($202.90, due 2026-10-25) is paid
with the default method 'Bank account ending 4821' (paid 2026-09-23), and his
account mailing address becomes 789 Oak Street, Oak Park, IL 60302. The DB
carries exactly: one bob login_events insert, the one Due->Paid bill flip with
method, bob's old mailing address superseded (is_current=0) + exactly one new
current row, and nothing else anywhere.
"""

from verify_lib import (BOB_DUE_BILL_AMOUNT, BOB_DUE_BILL_DUE_DATE, BOB_EMAIL,
                        DEFAULT_PAYMENT_LABEL, Judge, NEW_ADDRESS_BOB,
                        MIRROR_REFERENCE_DATE, advisory_llm_answer,
                        check_login_delta, check_signed_in_as,
                        check_table_delta_shape, check_trajectory_identity,
                        contains_money, contains_phrase, contains_phone,
                        final_answer, mailing_addresses_of, navigated_to_path,
                        premium_bills_of, run_verifier, user_id_by_email)

TASK_ID = "Medicare.gov--8"
FRAUD_PAGE = "/basics/reporting-medicare-fraud-and-abuse"
GROUND_TRUTH = ("The I-MEDIC phone number for reporting Medicare Advantage or drug plan "
                "fraud is 1-877-7SAFERX (1-877-772-3379). The due Part B premium of "
                "$202.90 was paid with the default payment method 'Bank account ending "
                "4821', and the account mailing address is now 789 Oak Street, Oak Park, "
                "IL 60302.")
QUESTION = ("Bob suspects fraudulent billing: what is the I-MEDIC number to report Medicare "
            "Advantage or drug plan fraud, then pay the due Part B premium with the default "
            "method and update the account mailing address to 789 Oak Street, Oak Park, IL "
            "60302. Confirm each change.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL)
    judge.check("opened_fraud_page",
                navigated_to_path(traj, FRAUD_PAGE),
                f"required_path={FRAUD_PAGE}")
    judge.check("opened_premiums_page", navigated_to_path(traj, "/my/premiums"),
                "required_path=/my/premiums")
    judge.check("opened_account_settings", navigated_to_path(traj, "/my/account-settings"),
                "required_path=/my/account-settings")
    judge.check("answer_imedic_number",
                contains_phone(answer, "8777723379") or contains_phrase(answer, "7SAFERX"),
                "expected 1-877-7SAFERX (1-877-772-3379)")
    judge.check("answer_paid_202_90",
                contains_money(answer, 202, 90) and contains_phrase(answer, "paid"),
                "expected the $202.90 premium paid")
    judge.check("answer_payment_method",
                contains_phrase(answer, "bank account") and contains_phrase(answer, "4821"),
                "expected 'Bank account ending 4821'")
    line1, city, state, zip_ = NEW_ADDRESS_BOB
    judge.check("answer_new_address",
                contains_phrase(answer, line1) and contains_phrase(answer, city)
                and contains_phrase(answer, zip_),
                f"expected the new address {NEW_ADDRESS_BOB!r}")

    # DB: exactly one login + the premium bill flip + the address supersede/insert
    user_id = user_id_by_email(initial_db, BOB_EMAIL)
    check_login_delta(judge, initial_db, after_db, BOB_EMAIL,
                      extra_allowed=("premium_bills", "mailing_addresses"))
    before, after = premium_bills_of(initial_db, user_id), premium_bills_of(after_db, user_id)
    due_before = [b for b in before if b["status"] == "Due" and b["due_date"] == BOB_DUE_BILL_DUE_DATE
                  and b["amount"] == BOB_DUE_BILL_AMOUNT]
    judge.check("seed_has_one_due_bill", len(due_before) == 1,
                f"due_bills_in_seed={due_before!r}")
    paid_after = [b for b in after if b["due_date"] == BOB_DUE_BILL_DUE_DATE
                  and b["amount"] == BOB_DUE_BILL_AMOUNT]
    ok = (len(paid_after) == 1 and paid_after[0]["status"] == "Paid"
          and paid_after[0]["paid_date"] == MIRROR_REFERENCE_DATE
          and paid_after[0]["method"] == DEFAULT_PAYMENT_LABEL)
    judge.check("premium_bill_due_to_paid", ok, f"bill_after={paid_after!r}")
    check_table_delta_shape(judge, initial_db, after_db, "premium_bills",
                            allowed_changed_ids=(3,),
                            label="premium_bills_only_due_bill_changed")
    other_changed = [b for b in after if b["due_date"] == "2026-09-25" and
                     not (b["status"] == "Paid" and b["method"] == "Direct deposit (bank account ending 4821)"
                          and b["paid_date"] == "2026-09-21")]
    judge.check("other_paid_bill_untouched", not other_changed,
                f"unexpected mutations of the pre-paid bill: {other_changed!r}")
    before_addr, after_addr = mailing_addresses_of(initial_db, user_id), mailing_addresses_of(after_db, user_id)
    old = [a for a in before_addr if a["is_current"]]
    judge.check("seed_has_one_current_address", len(old) == 1, f"current_in_seed={old!r}")
    superseded = [a for a in after_addr if a["id"] == old[0]["id"] and a["is_current"] == 0]
    new_rows = [a for a in after_addr if a["id"] not in {x["id"] for x in before_addr}]
    ok = (len(superseded) == 1 and len(new_rows) == 1 and new_rows[0]["line1"] == line1
          and new_rows[0]["city"] == city and new_rows[0]["state"] == state
          and new_rows[0]["zip"] == zip_ and new_rows[0]["is_current"] == 1
          and str(new_rows[0]["effective_date"]) == MIRROR_REFERENCE_DATE)
    judge.check("mailing_address_superseded_and_inserted", ok,
                f"new_rows={new_rows!r}, superseded={len(superseded)}")
    check_table_delta_shape(judge, initial_db, after_db, "mailing_addresses",
                            allowed_changed_ids=(old[0]["id"],), allowed_added=1,
                            label="mailing_addresses_only_bob_supersede")
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
