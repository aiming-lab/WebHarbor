#!/usr/bin/env python3
"""Verify SoundCloud--20.

Sign in as Alice (alice.j@test.com / TestPass123!). She has a paid listener plan but is considering Next Pro for her uploads. Check the plans page and report her current plan's name and monthly price from the banner. Switch her to the monthly Next Pro plan with card 4242 4242 4242 4242, and report the new plan's monthly price, the renewal date from the confirmation page, and how much more per month she'll pay than before. To make sure the switch stuck, sign out and sign back in, then report what the current-plan banner shows.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--20"

USER_ID = 1                       # Alice
OLD_PLAN = "Go+"
OLD_AMOUNT = 1199
NEW_PLAN_CODE = "next-pro"
NEW_PLAN_TITLE = "Next Pro"
NEW_AMOUNT = 1599
RENEWS = "2026-10-26"
DIFFERENCE = 400                   # $4.00 more per month


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_plans", r"/upgrade")
    check_visited_path(judge, traj, "visited_confirmation", r"/upgrade/done")
    check_answer_phrase(judge, answer, "old_plan_name", OLD_PLAN)
    judge.check("old_plan_price", "$11.99" in answer,
                "answer must report the old plan's $11.99 monthly price")
    check_answer_phrase(judge, answer, "new_plan_name", NEW_PLAN_TITLE)
    judge.check("new_plan_price", "$15.99" in answer,
                "answer must report the new plan's $15.99 monthly price")
    judge.check("difference", ("$4.00" in answer) or ("4.00 more" in answer)
                or ("$4 more" in answer),
                "answer must report the $4.00/month difference")
    judge.check("renewal_date",
                ("october 26, 2026" in answer.casefold())
                or ("oct 26 2026" in answer.casefold())
                or ("2026-10-26" in answer),
                "answer must report the renewal date October 26, 2026")
    # persistence: the banner after sign-out/sign-in must show Next Pro
    judge.check("banner_after_relogin",
                answer.casefold().count("next pro") >= 2
                and ("current plan" in answer.casefold() or "banner" in answer.casefold()),
                "answer must report the current-plan banner after signing back in")

    # DB after-state: Alice's Go+ subscription row is replaced by exactly one
    # new Next Pro monthly row (id 3), and nothing else changes.
    check_only_tables_changed(judge, initial_db, after_db, allowed={"subscriptions"})
    a, r, c = table_diff(initial_db, after_db, "subscriptions")
    judge.check("one_added_one_removed",
                len(a) == 1 and len(r) == 1 and not c,
                f"added={list(a.values())!r} removed={list(r.values())!r} changed={list(c.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("subscription_row",
                    row["user_id"] == USER_ID and row["plan_code"] == NEW_PLAN_CODE
                    and row["plan_title"] == NEW_PLAN_TITLE
                    and row["cycle"] == "monthly" and row["amount"] == NEW_AMOUNT
                    and str(row["renews_at"]).startswith(RENEWS)
                    and row["card_last4"] == "4242",
                    f"row={dict(row)}")
    if r:
        row = list(r.values())[0]
        judge.check("removed_old_subscription",
                    row["user_id"] == USER_ID and row["plan_code"] == "go-plus"
                    and row["amount"] == OLD_AMOUNT,
                    f"row={dict(row)}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
