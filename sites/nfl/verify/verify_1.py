#!/usr/bin/env python3
"""Verify NFL--1.

Create a new account for the user's sister (any realistic name/email, favorite
team Chicago Bears), subscribe her to the cheapest monthly plan, pay with any
valid test card, and report the order reference, the total charged, and the
exact date her subscription renews.

Frozen ground truth (app constants): the cheapest monthly plan is NFL+ Monthly
$6.99; tax = round(6.99 * 0.0895, 2) = $0.63; total = $7.62. A monthly
subscription renews 30 days after the frozen mirror date 2026-09-24 →
2026-10-24 (Oct 24, 2026). The order reference is deterministic for the 5th
user ("NFL-" + sha256(user_id:code:MIRROR_DATE)[:6]) = NFL-D0768F; the
verifier matches the ADDED order row by amount and requires the answer to name
that row's reference. DB delta: one users row (favorite_team CHI), one
plus_orders row (7.62), one active nfl_plus_monthly subscription renews
2026-10-24; nothing else changes.
"""
from verify_lib import (Judge, active_subscription, check_only_tables_changed,
                        check_precise_delta, check_trajectory_identity,
                        contains_amount, contains_date,
                        contains_phrase, final_answer, navigated_to, navigated_to_path,
                        orders_of, run_verifier)

TASK_ID = "NFL--1"
PLAN_CODE = "nfl_plus_monthly"
PLAN_TITLE = "NFL+ Monthly"
AMOUNT = 6.99
TAX = 0.63
TOTAL = 7.62
RENEWAL_DATE = "2026-10-24"
ORDER_REF = "NFL-D0768F"  # deterministic for the 5th user on a fresh reset


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-up, plans page, Monthly checkout, confirmation, account
    judge.check("visited_signup", navigated_to_path(traj, "/account/signup/"),
                "required: /account/signup/")
    judge.check("visited_plus_plans", navigated_to_path(traj, "/plus/"),
                "required: /plus/")
    judge.check("visited_monthly_checkout",
                navigated_to_path(traj, f"/plus/subscribe/{PLAN_CODE}/"),
                f"required: /plus/subscribe/{PLAN_CODE}/ (cheapest monthly plan)")
    judge.check("visited_confirmation", navigated_to(traj, "/plus/confirmation/"),
                "required: /plus/confirmation/<ref>")
    judge.check("visited_account", navigated_to_path(traj, "/account/"),
                "required: /account/ (renewal date is shown there)")
    # answer gates
    judge.check("answer_total_7_62", contains_amount(answer, TOTAL),
                f"expected total charged ${TOTAL:.2f} (6.99 + 0.63 tax)")
    judge.check("answer_renewal_oct_24_2026", contains_date(answer, RENEWAL_DATE),
                "expected renewal date October 24, 2026 (mirror date + 30 days)")
    # DB after-state: exactly one new user + order + subscription
    from verify_lib import added_rows
    new_users = added_rows(after_db, initial_db, "users", "email")
    judge.check("one_user_added", len(new_users) == 1, f"new_users={new_users!r}")
    if new_users:
        u = new_users[0]
        judge.check("new_user_favorite_chi", u["favorite_team"] == "CHI",
                    f"favorite_team={u['favorite_team']!r} (Chicago Bears)")
        judge.check("answer_names_ref_of_added_order",
                    contains_phrase(answer, ORDER_REF),
                    f"expected order reference {ORDER_REF} for the 5th user")
        sub = active_subscription(after_db, u["id"])
        judge.check("active_monthly_subscription",
                    sub is not None and sub["plan_code"] == PLAN_CODE
                    and sub["plan_title"] == PLAN_TITLE
                    and abs(sub["amount"] - AMOUNT) < 0.011
                    and str(sub["renews_at"]).startswith(RENEWAL_DATE),
                    f"subscription={sub!r}")
        orders = orders_of(after_db, u["id"])
        judge.check("one_order_row", len(orders) == 1
                    and orders[0]["order_ref"] == ORDER_REF
                    and abs(orders[0]["amount"] - AMOUNT) < 0.011
                    and abs(orders[0]["tax"] - TAX) < 0.011
                    and abs(orders[0]["total"] - TOTAL) < 0.011,
                    f"orders={orders!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "plus_orders", "subscriptions"))
    check_precise_delta(judge, initial_db, after_db, "users", "id", added_keys=(5,))
    # seed holds subscriptions 1-3 and plus_orders 1-2 (byte-identical to the
    # r1/r2/r3 reference seed, md5 f2d6879f); a brand-new user's single checkout
    # therefore adds subscription id 4 and order id 3. The original (5,)/(4,)
    # expectations were an off-by-one that no honest run could ever satisfy
    # (task 1 was never live-verified in r1 — only tasks 0 and 3 were).
    check_precise_delta(judge, initial_db, after_db, "subscriptions", "id", added_keys=(4,))
    check_precise_delta(judge, initial_db, after_db, "plus_orders", "id", added_keys=(3,))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
