#!/usr/bin/env python3
"""Verify NFL--15.

Compare the four NFL+ plans (name, price, billing cycle, RedZone); then sign in
as David Kim and switch him from the annual Premium plan to Premium Monthly,
paying with a valid test card in his name; report his old plan and price, the
new order reference and total charged including tax, his new renewal date, and
whether the monthly plan costs more or less per year (show the math).

Frozen ground truth (seed DB + app constants): the four plans — NFL+ Monthly
$6.99/mo, NFL+ Annual $49.99/yr, NFL+ Premium Monthly $14.99/mo (RedZone),
NFL+ Premium Annual $99.99/yr (RedZone). David is on NFL+ Premium Annual
($99.99). The switch to Premium Monthly: tax = round(14.99 * 0.0895, 2) = $1.34;
total = $16.33; the order reference is deterministic for user 4 ("NFL-" +
sha256(user_id:code:MIRROR_DATE)[:6].upper()) = NFL-D6DE08; the monthly
subscription renews 2026-10-24 (mirror date + 30 days). Per-year math: 14.99 x
12 = 179.88 vs 99.99 — the monthly plan costs $79.89 MORE per year. DB delta:
David's Premium Annual subscription (id 3) flips to cancelled, a new active
Premium Monthly subscription (id 4) is added, one plus_orders row (id 3) is
added; nothing else changes.
"""
from verify_lib import (Judge, check_only_tables_changed, check_precise_delta,
                        check_trajectory_identity,
                        contains_amount, contains_date, contains_phrase, final_answer,
                        navigated_to, navigated_to_path,
                        orders_of, run_verifier, subscriptions_of, user_by_email)

TASK_ID = "NFL--15"
DAVID_EMAIL = "david.k@test.com"
PLANS = (("NFL+ Monthly", 6.99), ("NFL+ Annual", 49.99),
         ("NFL+ Premium Monthly", 14.99), ("NFL+ Premium Annual", 99.99))
OLD_PLAN = "NFL+ Premium Annual"
OLD_PRICE = 99.99
NEW_CODE = "nfl_plus_premium_monthly"
NEW_TITLE = "NFL+ Premium Monthly"
AMOUNT = 14.99
TAX = 1.34
TOTAL = 16.33
ORDER_REF = "NFL-D6DE08"
RENEWAL = "2026-10-24"
ANNUALIZED = 179.89
MONTHLY_MATH = 179.88


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the plans page (compare), sign-in, the Premium Monthly
    # checkout, the confirmation, and the account page (new renewal date)
    judge.check("visited_plus_plans", navigated_to_path(traj, "/plus/"),
                "required: /plus/ (compare the four plans)")
    judge.check("visited_signin", navigated_to_path(traj, "/account/signin/"),
                "required: /account/signin/")
    judge.check("visited_monthly_checkout",
                navigated_to_path(traj, f"/plus/subscribe/{NEW_CODE}/"),
                f"required: /plus/subscribe/{NEW_CODE}/")
    judge.check("visited_confirmation", navigated_to(traj, "/plus/confirmation/"),
                "required: /plus/confirmation/<ref>")
    judge.check("visited_account", navigated_to_path(traj, "/account/"),
                "required: /account/ (new renewal date)")
    # answer gates: all four plans + prices; the switch facts; the math
    for name, price in PLANS:
        judge.check(f"answer_plan_{name.lower().replace('+', '').replace(' ', '_')}",
                    contains_phrase(answer, name) and contains_amount(answer, price),
                    f"expected {name} at ${price:.2f}")
    judge.check("answer_redzone_in_premium",
                contains_phrase(answer, "RedZone") and contains_phrase(answer, "Premium"),
                "RedZone belongs to the two Premium plans")
    judge.check("answer_old_plan", contains_phrase(answer, OLD_PLAN),
                f"expected the old plan {OLD_PLAN}")
    judge.check("answer_old_price", contains_amount(answer, OLD_PRICE),
                f"expected the old price ${OLD_PRICE:.2f}")
    judge.check("answer_order_ref", contains_phrase(answer, ORDER_REF),
                f"expected the new order reference {ORDER_REF}")
    judge.check("answer_total_16_33", contains_amount(answer, TOTAL),
                f"expected the total charged ${TOTAL:.2f} (14.99 + 1.34 tax)")
    judge.check("answer_renewal_oct_24", contains_date(answer, RENEWAL),
                "expected the new renewal date October 24, 2026")
    judge.check("answer_monthly_costs_more", "more" in answer.lower(),
                "the monthly plan costs MORE per year — the answer must say so")
    judge.check("answer_shows_math",
                contains_amount(answer, MONTHLY_MATH) and "12" in answer
                and contains_amount(answer, ANNUALIZED),
                f"expected the math: 14.99 x 12 = {MONTHLY_MATH:.2f}, which is "
                f"${ANNUALIZED:.2f} more than 99.99")
    # DB after-state: exactly the plan switch
    david = user_by_email(after_db, DAVID_EMAIL)
    judge.check("david_exists", david is not None, f"david={DAVID_EMAIL}")
    if david:
        subs = subscriptions_of(after_db, david["id"])
        active = [s for s in subs if s["status"] == "active"]
        cancelled = [s for s in subs if s["status"] == "cancelled"]
        judge.check("one_active_premium_monthly",
                    len(active) == 1 and active[0]["plan_code"] == NEW_CODE
                    and active[0]["plan_title"] == NEW_TITLE
                    and abs(active[0]["amount"] - AMOUNT) < 0.011
                    and str(active[0]["renews_at"]).startswith(RENEWAL),
                    f"active={active!r}")
        judge.check("old_annual_cancelled",
                    len(cancelled) == 1 and cancelled[0]["plan_code"] == "nfl_plus_premium_annual",
                    f"cancelled={cancelled!r}")
        orders = orders_of(after_db, david["id"])
        judge.check("one_new_order_row", len(orders) == 2
                    and orders[1]["order_ref"] == ORDER_REF
                    and abs(orders[1]["amount"] - AMOUNT) < 0.011
                    and abs(orders[1]["tax"] - TAX) < 0.011
                    and abs(orders[1]["total"] - TOTAL) < 0.011,
                    f"orders={orders!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("plus_orders", "subscriptions"))
    check_precise_delta(judge, initial_db, after_db, "users", "id")
    check_precise_delta(judge, initial_db, after_db, "subscriptions", "id",
                        changed_keys=(3,), added_keys=(4,))
    check_precise_delta(judge, initial_db, after_db, "plus_orders", "id", added_keys=(3,))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
