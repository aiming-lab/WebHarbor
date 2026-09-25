#!/usr/bin/env python3
"""Verify NFL--2.

Carol (carol.d@test.com) cancels her NFL+ subscription, turns on the NFL
newsletter in her profile, sets a new password, signs out and back in with the
new password, and reports: the plan she was on and its per-cycle price, the
order reference and total of her original purchase, what her subscription
section shows after cancelling, her newsletter setting, and what her
homepage's My Team module says about the Cowboys' Week 3 game (opponent, day,
kickoff).

Frozen ground truth (seed DB): Carol is on NFL+ Annual at $49.99 per year; her
original order reference is NFL-03NUAL ($49.99 + $4.47 tax = $54.46). After a
correct cancellation the account shows "You don't have an active NFL+
subscription." The My Team module reads: Dallas Cowboys (1-1), Week 3
Baltimore Ravens at Dallas Cowboys — INTL SUN 4:25pm ET (the Rio international
game). DB delta: Carol's subscription (id 2) flips to cancelled and her users
row (id 3) changes (newsletter on + new password hash); nothing else changes.
"""
from verify_lib import (Judge, check_only_tables_changed, check_precise_delta,
                        check_trajectory_identity,
                        contains_amount, contains_phrase, contains_time, entered_identity,
                        final_answer, navigated_to, navigated_to_path,
                        orders_of, run_verifier, subscriptions_of, user_by_email)

TASK_ID = "NFL--2"
CAROL_EMAIL = "carol.d@test.com"
PLAN_TITLE = "NFL+ Annual"
CYCLE_AMOUNT = 49.99
ORDER_REF = "NFL-03NUAL"
ORDER_TOTAL = 54.46
NEW_PASSWORD = "CarolFan2026!"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, the account page (plan + history + cancel), the
    # profile edit (newsletter + password), sign-out, sign-in again, homepage
    judge.check("visited_signin", navigated_to_path(traj, "/account/signin/"),
                "required: /account/signin/")
    judge.check("visited_account", navigated_to_path(traj, "/account/"),
                "required: /account/")
    judge.check("visited_cancel", navigated_to_path(traj, "/account/cancel-subscription/"),
                "required: /account/cancel-subscription/")
    judge.check("visited_profile_edit", navigated_to_path(traj, "/account/edit/"),
                "required: /account/edit/ (newsletter + new password)")
    judge.check("visited_signout", navigated_to_path(traj, "/account/signout/"),
                "required: /account/signout/")
    signin_visits = sum(1 for u in [s.get("url", "") for s in traj.get("steps", [])]
                        if "/account/signin/" in str(u))
    judge.check("signed_in_twice", signin_visits >= 2,
                "required: sign in, then sign out and sign back in with the new password")
    judge.check("typed_new_password", entered_identity(traj, NEW_PASSWORD),
                f"required: the new password {NEW_PASSWORD!r} typed at re-login")
    judge.check("visited_homepage_my_team", navigated_to_path(traj, "/"),
                "required: / (My Team module)")
    # answer gates
    judge.check("answer_plan_annual", contains_phrase(answer, PLAN_TITLE),
                f"expected plan {PLAN_TITLE}")
    judge.check("answer_cycle_amount", contains_amount(answer, CYCLE_AMOUNT),
                f"expected per-cycle price ${CYCLE_AMOUNT:.2f}")
    judge.check("answer_order_ref", contains_phrase(answer, ORDER_REF),
                f"expected original order reference {ORDER_REF}")
    judge.check("answer_order_total", contains_amount(answer, ORDER_TOTAL),
                f"expected original order total ${ORDER_TOTAL:.2f}")
    judge.check("answer_cancelled_status",
                any(p in answer.lower() for p in
                    ("cancel", "no active", "don't have an active", "inactive", "ended")),
                "answer must state the post-cancellation status")
    judge.check("answer_newsletter_on",
                any(p in answer.lower() for p in ("newsletter on", "newsletter is on",
                                                   "subscribed to the newsletter",
                                                   "newsletter now on", "newsletter: on")),
                "answer must state the newsletter setting is on")
    judge.check("answer_my_team_cowboys", contains_phrase(answer, "Cowboys"),
                "expected the Cowboys as Carol's favorite team")
    judge.check("answer_my_team_opponent_ravens", contains_phrase(answer, "Ravens"),
                "expected the Ravens as the Week 3 opponent")
    judge.check("answer_my_team_kickoff", contains_time(answer, "16:25"),
                "expected INTL SUN 4:25pm ET kickoff in the My Team module")
    # DB after-state: exactly Carol's subscription flips to cancelled + her user row
    carol = user_by_email(after_db, CAROL_EMAIL)
    judge.check("carol_exists", carol is not None, f"carol={CAROL_EMAIL}")
    if carol:
        judge.check("carol_newsletter_on", bool(carol["newsletter"]),
                    f"newsletter={carol['newsletter']!r}")
        seed_carol = user_by_email(initial_db, CAROL_EMAIL)
        judge.check("carol_password_changed",
                    carol["password_hash"] != seed_carol["password_hash"],
                    "password hash must differ from the seed after the password change")
        subs = subscriptions_of(after_db, carol["id"])
        judge.check("subscription_cancelled_in_db",
                    len(subs) == 1 and subs[0]["status"] == "cancelled"
                    and subs[0]["plan_code"] == "nfl_plus_annual",
                    f"subscriptions={subs!r}")
        orders = orders_of(after_db, carol["id"])
        judge.check("order_history_untouched",
                    len(orders) == 1 and orders[0]["order_ref"] == ORDER_REF,
                    f"orders={orders!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users", "subscriptions"))
    check_precise_delta(judge, initial_db, after_db, "users", "id", changed_keys=(3,))
    check_precise_delta(judge, initial_db, after_db, "subscriptions", "id", changed_keys=(2,))
    check_precise_delta(judge, initial_db, after_db, "plus_orders", "id")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
