#!/usr/bin/env python3
"""Verify Ohio.gov--10.

Bob's alert chain: sign in, read the Ohio Benefits self-service portal alert
(during which hours it will be unavailable), subscribe to "Unemployment
system" alerts and to "Outage notifications" alerts — each with the account's
own email — then report how many alert subscriptions the account page lists
now and the title of the alert about BMV online services.

Frozen ground truth (seed DB): bob_c already carries one "Ohio Business
Gateway" subscription (bob.c@test.com). The alerts page item "Ohio Benefits
self-service portal maintenance" says the portal will be unavailable Sunday,
September 20 from 2:00 AM to 6:00 AM for scheduled maintenance. After the task
the account holds exactly 3 subscriptions — "Ohio Business Gateway" (seed),
"Unemployment system", and "Outage notifications" — all at bob.c@test.com,
with no duplicate rows. The alerts page lists the item "BMV Online Services:
scheduled outage".
"""
from verify_lib import (SEED_USERS, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, entered_identity, final_answer, run_verifier,
                        subscriptions_of)

TASK_ID = "Ohio.gov--10"
BOB_ID = SEED_USERS["bob.c@test.com"][0]
BOB_EMAIL = "bob.c@test.com"
EXPECTED_TYPES = {"Ohio Business Gateway", "Unemployment system", "Outage notifications"}
BMV_ALERT_TITLE = "bmv online services: scheduled outage"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL)
    # navigation gates: the alerts page (read + subscribe twice) + account
    check_visited_path(judge, traj, "visited_alerts_page", "/alerts")
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("subscribed_with_own_email",
                entered_identity(traj, BOB_EMAIL),
                f"expected {BOB_EMAIL!r} in the subscribe form inputs")
    # DB after-state: exactly 3 subscriptions, the seed one + the two new
    # types, all with the account's own email, no duplicates
    subs = subscriptions_of(after_db, BOB_ID)
    types = [s["alert_type"] for s in subs]
    judge.check("three_subscriptions", len(subs) == 3,
                f"observed={types!r}")
    judge.check("subscriptions_exact_types",
                set(types) == EXPECTED_TYPES,
                f"observed={types!r}")
    judge.check("subscriptions_no_duplicates",
                len(types) == len(set(types)),
                f"observed={types!r}")
    judge.check("subscriptions_own_email",
                all((s["email"] or "").lower() == BOB_EMAIL for s in subs),
                f"observed={[s['email'] for s in subs]!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("alert_subscriptions",))
    # answer: unavailability hours + subscription count + BMV alert title
    judge.check("answer_benefits_unavailable_hours",
                contains_phrase(answer, "2:00 am") and contains_phrase(answer, "6:00 am"),
                "expected: unavailable Sunday, September 20 from 2:00 AM to 6:00 AM")
    judge.check("answer_subscription_count", contains_count(answer, 3),
                "expected: 3 alert subscriptions listed")
    judge.check("answer_bmv_alert_title", contains_phrase(answer, BMV_ALERT_TITLE),
                f"expected alert title: {BMV_ALERT_TITLE!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
