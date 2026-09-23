#!/usr/bin/env python3
"""Verify League of Legends--15: profile edit persistence across sign-out/re-login.

Honest chain (22 atomic actions): Play Now -> Sign In -> fill email -> fill
password -> submit -> My Account -> Edit Profile -> fill summoner
'RadiantViper' -> select EUW -> Save Changes -> Sign Out -> Play Now ->
Sign In -> fill email -> fill password -> submit -> My Account (persisted
RadiantViper/EUW) -> Edit Profile -> select NA -> Save Changes -> My Account
(final RadiantViper/NA) -> answer.

Frozen ground truth (seed DB): alice_j (id 1) seeds summoner_name='StarlitFox',
region='NA'. The chain changes summoner_name to 'RadiantViper' and region to
'EUW', proves persistence across sign-out + re-login, then restores region to
'NA'. Database delta: exactly one users row change — alice's summoner_name
StarlitFox -> RadiantViper (region ends equal to the seeded NA) — and nothing
else.
"""
from verify_lib import (check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_user_profile_delta,
                        contains_phrase, final_answer, navigated_to_path,
                        run_verifier)

TASK_ID = "League of Legends--15"
EMAIL = "alice.j@test.com"
EXPECTED_CHANGE = {"summoner_name": ("StarlitFox", "RadiantViper")}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_profile_edit", navigated_to_path(traj, "/account/profile"),
                "required: /account/profile")
    judge.check("visited_signin_page", navigated_to_path(traj, "/login"),
                "required: /login (sign out then sign in again)")
    judge.check("visited_account", navigated_to_path(traj, "/account"),
                "required: /account")

    judge.check("answer_new_summoner", contains_phrase(answer, "RadiantViper"),
                "expected 'RadiantViper' reported as the new summoner name")
    judge.check("answer_first_change_euw", contains_phrase(answer, "EUW"),
                "expected EUW reported after the first change")
    judge.check("answer_persistence_confirmed",
                contains_phrase(answer, "persist") or contains_phrase(answer, "still")
                or contains_phrase(answer, "after signing in again")
                or contains_phrase(answer, "after signing back in"),
                "expected the persistence across re-login confirmed")
    judge.check("answer_final_region_na", contains_phrase(answer, "NA"),
                "expected NA reported as the final region")

    check_user_profile_delta(judge, initial_db, after_db, 1, EXPECTED_CHANGE)
    check_only_tables_changed(judge, initial_db, after_db, {"users"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
