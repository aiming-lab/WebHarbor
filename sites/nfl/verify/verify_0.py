#!/usr/bin/env python3
"""Verify NFL--0.

Bob (bob.c@test.com) pays month-to-month for NFL+ Premium but hates monthly
bills. Sign in with his demo account, switch him to the annual plan that
includes NFL RedZone, pay with a valid Visa card in his name ending in 4242,
switch on the NFL newsletter, and report the order reference, the total
charged including tax, the plan and renewal date his account now shows, and
what his homepage's My Team module says about his favorite team's Week 3 game
(opponent, day, kickoff).

Frozen ground truth (seed DB + app constants): Bob starts on NFL+ Premium
Monthly ($14.99/mo). The annual RedZone plan is NFL+ Premium Annual $99.99;
tax = round(99.99 * 0.0895, 2) = $8.95; total = $108.94. The order reference
is deterministic ("NFL-" + sha256(user_id:code:MIRROR_DATE)[:6].upper()) =
NFL-47C7FF. The account shows NFL+ Premium Annual renews September 24, 2027.
The My Team module reads: Green Bay Packers (1-1), Week 3 Atlanta Falcons at
Green Bay Packers — THU 8:15pm ET. DB delta: Bob's old subscription flips to
cancelled, a new active Premium Annual subscription (id 4), one plus_orders
row (id 3), and Bob's users row flips newsletter 0 -> 1; nothing else changes.
"""
from verify_lib import (Judge, check_only_tables_changed, check_precise_delta,
                        check_trajectory_identity,
                        contains_amount, contains_date, contains_phrase, contains_time,
                        final_answer, navigated_to, navigated_to_path,
                        orders_of, run_verifier, subscriptions_of, user_by_email)

TASK_ID = "NFL--0"
BOB_EMAIL = "bob.c@test.com"
TOTAL = 108.94
AMOUNT = 99.99
TAX = 8.95
ORDER_REF = "NFL-47C7FF"
NEW_PLAN_CODE = "nfl_plus_premium_annual"
NEW_PLAN_TITLE = "NFL+ Premium Annual"
RENEWAL = "2027-09-24"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, the NFL+ plans page, the Premium Annual checkout,
    # the confirmation, the account area, the profile edit (newsletter), and the
    # homepage (My Team module)
    judge.check("visited_signin", navigated_to_path(traj, "/account/signin/"),
                "required: /account/signin/")
    judge.check("visited_plus_plans", navigated_to_path(traj, "/plus/"),
                "required: /plus/ (compare plans, pick the annual RedZone plan)")
    judge.check("visited_premium_annual_checkout",
                navigated_to_path(traj, f"/plus/subscribe/{NEW_PLAN_CODE}/"),
                f"required: /plus/subscribe/{NEW_PLAN_CODE}/")
    judge.check("visited_confirmation", navigated_to(traj, "/plus/confirmation/"),
                "required: /plus/confirmation/<ref>")
    judge.check("visited_account", navigated_to_path(traj, "/account/"),
                "required: /account/ (plan + renewal date after the switch)")
    judge.check("visited_profile_edit", navigated_to_path(traj, "/account/edit/"),
                "required: /account/edit/ (newsletter switch)")
    judge.check("visited_homepage_my_team", navigated_to_path(traj, "/"),
                "required: / (My Team module)")
    # answer gates: order reference + charged total + plan/renewal + My Team facts
    judge.check("answer_order_ref", contains_phrase(answer, ORDER_REF),
                f"expected order reference {ORDER_REF}")
    judge.check("answer_total_108_94", contains_amount(answer, TOTAL),
                f"expected total charged ${TOTAL:.2f} (99.99 + 8.95 tax)")
    judge.check("answer_plan_premium_annual", contains_phrase(answer, NEW_PLAN_TITLE),
                f"expected the account to show {NEW_PLAN_TITLE}")
    judge.check("answer_renewal_sept_24_2027", contains_date(answer, RENEWAL),
                "expected renewal date September 24, 2027")
    judge.check("answer_my_team_packers", contains_phrase(answer, "Packers"),
                "expected the Packers as Bob's favorite team")
    judge.check("answer_my_team_opponent_falcons", contains_phrase(answer, "Falcons"),
                "expected the Falcons as the Week 3 opponent")
    judge.check("answer_my_team_thu_kickoff", contains_time(answer, "20:15"),
                "expected THU 8:15pm ET kickoff in the My Team module")
    # DB after-state: exactly the plan switch + the newsletter flip
    bob = user_by_email(after_db, BOB_EMAIL)
    judge.check("bob_exists", bob is not None, f"bob={BOB_EMAIL}")
    if bob:
        judge.check("bob_newsletter_on", bool(bob["newsletter"]),
                    f"newsletter={bob['newsletter']!r} (must be switched on)")
        subs = subscriptions_of(after_db, bob["id"])
        active = [s for s in subs if s["status"] == "active"]
        cancelled = [s for s in subs if s["status"] == "cancelled"]
        judge.check("one_active_premium_annual",
                    len(active) == 1 and active[0]["plan_code"] == NEW_PLAN_CODE
                    and active[0]["plan_title"] == NEW_PLAN_TITLE
                    and abs(active[0]["amount"] - AMOUNT) < 0.011
                    and str(active[0]["renews_at"]).startswith(RENEWAL),
                    f"active={active!r}")
        judge.check("old_monthly_cancelled",
                    len(cancelled) == 1 and cancelled[0]["plan_code"] == "nfl_plus_premium_monthly",
                    f"cancelled={cancelled!r}")
        orders = orders_of(after_db, bob["id"])
        judge.check("one_new_order_row", len(orders) == 1
                    and orders[0]["order_ref"] == ORDER_REF
                    and abs(orders[0]["amount"] - AMOUNT) < 0.011
                    and abs(orders[0]["tax"] - TAX) < 0.011
                    and abs(orders[0]["total"] - TOTAL) < 0.011
                    and orders[0]["card_last4"] == "4242"
                    and (orders[0]["cardholder"] or "").lower() == "bob chen",
                    f"orders={orders!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "plus_orders", "subscriptions"))
    check_precise_delta(judge, initial_db, after_db, "users", "id", changed_keys=(2,))
    check_precise_delta(judge, initial_db, after_db, "subscriptions", "id",
                        changed_keys=(1,), added_keys=(4,))
    check_precise_delta(judge, initial_db, after_db, "plus_orders", "id", added_keys=(3,))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
