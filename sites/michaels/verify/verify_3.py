#!/usr/bin/env python3
"""Verify Michaels--3.

Alice needs an expense-report summary of her Michaels pickup order that used a 30% off promo code. Prepare the summary: the order number, its current status, each item with its color and quantity, and exactly how the promo discount, shipping, and tax add up to the order total. Also state which store the pickup was scheduled at. Sign in as alice.j@test.com with password TestPass123!.
"""
from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_all, contains_amount, contains_any,
                        contains_count, contains_phrase, final_answer, navigated_account_order,
                        run_verifier)

TASK_ID = "Michaels--3"
ORDER_NUMBER = "MI2609180101002"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, account orders, the order's detail page
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("visited_order_detail", navigated_account_order(traj, ORDER_NUMBER),
                f"required: /account/order/{ORDER_NUMBER}")
    # answer: all the expense-report facts
    judge.check("answer_order_number", contains_phrase(answer, ORDER_NUMBER),
                f"expected order number {ORDER_NUMBER}")
    judge.check("answer_status", contains_phrase(answer, "Delivered"),
                "expected status Delivered")
    judge.check("answer_item", contains_phrase(answer, "Tulle Fabric") and
                contains_count(answer, 6) and contains_phrase(answer, "White"),
                "expected 6 x Tulle Fabric (White)")
    judge.check("answer_subtotal", contains_amount(answer, 29.94),
                "expected subtotal $29.94")
    judge.check("answer_discount", contains_amount(answer, 8.98),
                "expected promo discount $8.98")
    judge.check("answer_shipping", contains_phrase(answer, "FREE") or
                contains_amount(answer, 0),
                "expected FREE shipping")
    judge.check("answer_tax", contains_amount(answer, 1.94),
                "expected tax $1.94")
    judge.check("answer_total", contains_amount(answer, 22.90),
                "expected total $22.90")
    judge.check("answer_card", contains_all(answer, ["Visa", "4242"]),
                "expected Visa ****4242")
    judge.check("answer_store", contains_any(answer, ["Parkway Supercenter", "Tukwila"]),
                "expected the pickup store (Parkway Supercenter, Tukwila)")
    # read-only task: DB must be untouched
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
