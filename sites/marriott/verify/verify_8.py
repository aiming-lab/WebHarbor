#!/usr/bin/env python3
"""Verify Marriott--8.

Sign in as bob.c@test.com. Office moved: update the profile with phone
+1 415-555-0123, street 1200 Broadway, city Oakland, state California; sign out
and sign back in to confirm persistence; report the exact success message shown
right after saving.

Frozen ground truth: profile save flashes "Your profile has been updated."; bob's
seed profile (88 King Street, San Francisco) must change to exactly the new
values and nothing else on the account domain.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        final_answer, input_texts, run_verifier, table_delta, user_by_email)

TASK_ID = "Marriott--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_profile_page", "/loyalty/myAccount/profile.mi")
    email_fills = input_texts(traj)
    judge.check("signed_out_and_back_in",
                email_fills.count("bob.c@test.com") >= 2
                and sum(1 for s in (traj.get("steps") or [])
                        if isinstance(s, dict) and "sign-in.mi" in str(s.get("url", ""))) >= 2,
                "required: the account signed in twice (sign out + sign back in): "
                f"email_fills={email_fills!r}")
    judge.check("answer_success_message", contains_phrase(answer, "Your profile has been updated."),
                "expected the exact success message 'Your profile has been updated.'")
    # DB after-state: bob's profile fields updated to the task's values, users
    # table otherwise untouched, no other table changed
    bob = user_by_email(after_db, "bob.c@test.com")
    judge.check("profile_phone", bob and bob["phone"] == "+1 415-555-0123",
                f"expected phone +1 415-555-0123, observed={bob and bob['phone']!r}")
    judge.check("profile_street", bob and bob["street_address"] == "1200 Broadway",
                f"expected street 1200 Broadway, observed={bob and bob['street_address']!r}")
    judge.check("profile_city", bob and bob["city"] == "Oakland",
                f"expected city Oakland, observed={bob and bob['city']!r}")
    judge.check("profile_state", bob and bob["state"] == "California",
                f"expected state California, observed={bob and bob['state']!r}")
    delta = table_delta(initial_db, after_db, "users")
    changed_ok = (len(delta["added"]) == 0 and len(delta["removed"]) == 0
                  and len(delta["changed"]) == 1)
    judge.check("only_bob_row_changed", changed_ok,
                f"expected exactly one changed users row (bob); delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
