#!/usr/bin/env python3
"""Verify Public Storage--11 (read-only) — r2 task text.

Does it cost anything to hold a storage unit, and how long does a hold last?
When is a late fee applied to a monthly storage bill? What one-time fee are
new rentals subject to, what should you bring on move-in day, and who
receives gate codes and what should you do if you lose yours? Find these
answers in the Help Center and report each answer together with the topic
page it came from.

Frozen ground truth (seed DB): the Reservations & Holds topic says a hold
carries no payment and lasts seven days. The Billing & Payments topic says a
late fee applies if a monthly payment is more than five days past due. The
Renting & Move-In topic says new rentals are subject to a one-time $29
administration fee and to bring a government-issued photo ID. The Security
& Access topic says only tenants receive gate codes and to report a lost
code to the property manager.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_any_phrase, contains_phrase, final_answer,
                        navigated_help_home, navigated_help_topic, run_verifier)

TASK_ID = "Public Storage--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_help_home", navigated_help_home(traj),
                "required: help center")
    judge.check("visited_hold_topic", navigated_help_topic(traj, "reservations-and-holds"),
                "required: the Reservations & Holds topic page")
    judge.check("visited_billing_topic", navigated_help_topic(traj, "billing-and-payments"),
                "required: the Billing & Payments topic page")
    judge.check("visited_movein_topic", navigated_help_topic(traj, "renting-and-move-in"),
                "required: the Renting & Move-In topic page")
    judge.check("visited_security_topic", navigated_help_topic(traj, "security-and-access"),
                "required: the Security & Access topic page")
    # answers
    judge.check("answer_hold_cost",
                contains_any_phrase(answer, ["no payment", "at no cost", "free",
                                             "no obligation and no payment"]),
                "holding a unit costs nothing (no payment / free)")
    judge.check("answer_hold_duration",
                contains_any_phrase(answer, ["seven days", "7 days"]),
                "a hold lasts seven days")
    judge.check("answer_late_fee",
                contains_any_phrase(answer, ["five days past due", "5 days past due",
                                             "more than five days"]),
                "a late fee applies if a monthly payment is more than five days past due")
    judge.check("answer_admin_fee",
                contains_phrase(answer, "$29") or contains_phrase(answer, "29 dollar"),
                "new rentals are subject to a one-time $29 administration fee")
    judge.check("answer_bring_photo_id",
                contains_phrase(answer, "photo id"),
                "bring a government-issued photo ID on move-in day")
    judge.check("answer_gate_codes",
                contains_phrase(answer, "only tenants"),
                "only tenants receive gate codes")
    judge.check("answer_lost_code",
                contains_phrase(answer, "property manager"),
                "report a lost code to the property manager")
    # topic attribution
    judge.check("answer_topic_pages",
                contains_phrase(answer, "reservations")
                and contains_phrase(answer, "billing")
                and contains_phrase(answer, "renting")
                and contains_phrase(answer, "security"),
                "all four topic pages named (Reservations & Holds, Billing & "
                "Payments, Renting & Move-In, Security & Access)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
