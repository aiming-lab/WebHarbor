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
from verify_lib import (bound_phrase, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        check_user_profile_delta, contains_phrase, contains_stem,
                        final_answer, navigated_to_path, run_verifier)

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

    judge.check("answer_new_summoner",
                bound_phrase(answer, "RadiantViper", "summoner", ["region"], mode="after",
                             allow_misbound=True, optional_owner=True),
                "expected 'RadiantViper' attached to the summoner field")
    judge.check("answer_first_change_euw",
                bound_phrase(answer, "EUW", "region", ["summoner"], optional_owner=True),
                "expected EUW attached to the region field")
    judge.check("answer_persistence_confirmed",
                contains_stem(answer, "persist") or contains_phrase(answer, "still")
                or contains_phrase(answer, "after signing in again")
                or contains_phrase(answer, "after signing back in")
                or contains_phrase(answer, "signing out and signing in again"),
                "expected the persistence across re-login confirmed")
    judge.check("answer_final_region_na",
                bound_phrase(answer, "NA", "region", ["summoner"], optional_owner=True),
                "expected NA attached to the region field as the final state")

    check_user_profile_delta(judge, initial_db, after_db, 1, EXPECTED_CHANGE)
    check_only_tables_changed(judge, initial_db, after_db, {"users"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
