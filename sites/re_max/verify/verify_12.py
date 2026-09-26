#!/usr/bin/env python3
"""verify_12.py — deterministic verifier for task REMAX--12.

Register Maria Torres (Downsizer), update phone, subscribe Miami alerts; report buyer type + phone.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, added_rows, check_only_tables_changed, check_seed_contract,
    check_trajectory_identity, contains_any_phrase, contains_phrase,
    entered_identity, final_answer, nav_account, nav_account_edit, nav_register,
    nav_srp, run_verifier)

TASK_ID = "REMAX--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: registration + profile edit + Miami SRP alert signup
    judge.check("nav_register", nav_register(traj), "required: /register")
    judge.check("nav_account_edit", nav_account_edit(traj),
                "required: /account/edit")
    judge.check("nav_account", nav_account(traj), "required: /account")
    judge.check("entered_register_email",
                entered_identity(traj, "maria.torres@example.com"),
                "required: maria.torres@example.com entered on a form")
    judge.check("entered_phone", entered_identity(traj, "(305) 555-0134"),
                "required: phone (305) 555-0134 entered on a form")
    judge.check("nav_miami_srp", nav_srp(traj, "fl", "miami"),
                "required: /fl/miami-real-estate (alert signup)")
    # DB after-state: exactly one new user with the task's profile + one new
    # Miami listing alert, nothing else
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db,
                              ["users", "listing_alerts"])
    new_users = added_rows(after_db, initial_db, "users", "id")
    judge.check("exactly_one_new_user", len(new_users) == 1,
                f"new users: {new_users}")
    if new_users:
        u = new_users[0]
        judge.check("user_email",
                   (u["email"] or "").lower() == "maria.torres@example.com",
                   f"email={u['email']}")
        judge.check("user_name", u["first_name"] == "Maria" and u["last_name"] == "Torres",
                    f"name={u['first_name']} {u['last_name']}")
        judge.check("user_buyer_type", u["buyer_type"] == "Downsizer",
                    f"buyer_type={u['buyer_type']}")
        judge.check("user_phone", u["phone"] == "(305) 555-0134",
                    f"phone={u['phone']}")
    new_alerts = added_rows(after_db, initial_db, "listing_alerts", "id")
    judge.check("exactly_one_new_alert", len(new_alerts) == 1,
                f"new alerts: {new_alerts}")
    if new_alerts:
        a = new_alerts[0]
        judge.check("alert_email",
                   (a["email"] or "").lower() == "maria.torres@example.com",
                   f"email={a['email']}")
        judge.check("alert_city_state", a["city"] == "Miami" and a["state"] == "FL",
                    f"city/state={a['city']}/{a['state']}")
    # ground truth (frozen seed): account shows Downsizer + (305) 555-0134
    judge.check("answer_buyer_type", contains_phrase(answer, "Downsizer"),
                "must report buyer type Downsizer")
    judge.check("answer_phone",
                contains_any_phrase(answer, ["(305) 555-0134", "305-555-0134",
                                              "305.555.0134"]),
                "must report the phone (305) 555-0134")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
