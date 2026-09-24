#!/usr/bin/env python3
"""Verify Micro Center--7.

Log in as alice.j@test.com (password TestPass123!). I've moved — update the phone number on the profile to 919-555-0142 and add a new default shipping address: Dana Johnson, 730 Memorial Drive, Apt 5B, Cambridge, MA 02139, phone 617-555-8890. Report which address is now the default.
"""
from verify_lib import (addresses_of, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_phrase, final_answer,
                        navigated_to_path, run_verifier, user_by_email)

TASK_ID = "Micro Center--7"
EMAIL = "alice.j@test.com"
PHONE = "919-555-0142"
NEW_ADDRESS = {"full_name": "Dana Johnson", "line1": "730 Memorial Drive",
               "line2": "Apt 5B", "city": "Cambridge", "state": "MA",
               "zip_code": "02139", "phone": "617-555-8890"}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_profile_page", navigated_to_path(traj, "/account/profile"),
                "required_path=/account/profile")
    judge.check("visited_addresses_page", navigated_to_path(traj, "/account/addresses"),
                "required_path=/account/addresses")
    alice = user_by_email(after_db, EMAIL)
    judge.check("profile_phone_updated",
                alice is not None and alice["phone"] == PHONE,
                f"phone={alice['phone'] if alice else None!r}")
    addrs = addresses_of(after_db, EMAIL)
    new = [a for a in addrs if a["full_name"] == NEW_ADDRESS["full_name"]
           and a["line1"] == NEW_ADDRESS["line1"]
           and (a["line2"] or "") == NEW_ADDRESS["line2"]
           and a["city"] == NEW_ADDRESS["city"] and a["state"] == NEW_ADDRESS["state"]
           and a["zip_code"] == NEW_ADDRESS["zip_code"]]
    judge.check("new_address_row_exists", bool(new),
                f"addresses={[(a['full_name'], a['line1']) for a in addrs]!r}")
    if new:
        judge.check("new_address_is_default", new[0]["is_default"] == 1,
                    f"is_default={new[0]['is_default']!r}")
    others = [a for a in addrs if a not in new]
    judge.check("old_addresses_not_default",
                all(a["is_default"] == 0 for a in others),
                f"old_defaults={[(a['full_name'], a['is_default']) for a in others]!r}")
    judge.check("answer_names_new_default",
                contains_phrase(answer, "dana johnson"),
                "expected the Dana Johnson address as the new default")
    check_only_tables_changed(judge, initial_db, after_db, ("users", "addresses"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
