#!/usr/bin/env python3
"""Verify League of Legends--24: alice profile edit — summoner RadiantViper, region EUW (stateful)."""
from verify_lib import (SEED_USERS, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_phrase, final_answer,
                        navigated_to_path, run_verifier, table_delta, user_by_email)

TASK_ID = "League of Legends--24"
EMAIL = "alice.j@test.com"
SUMMONER = "RadiantViper"
REGION = "EUW"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_profile_page", navigated_to_path(traj, "/account/profile"),
                "required: /account/profile")
    judge.check("answer_summoner", contains_phrase(answer, SUMMONER),
                f"expected the summoner name {SUMMONER!r}")
    judge.check("answer_region", contains_phrase(answer, REGION), "expected the region EUW")
    # state: exactly the alice users row changed, and only summoner_name + region differ
    delta = table_delta(initial_db, after_db, "users")
    judge.check("users_changed_exactly_one_row",
                len(delta["changed"]) == 1 and not delta["added"] and not delta["removed"],
                f"expected exactly one changed users row; delta={delta!r}")
    if delta["changed"]:
        before, after = delta["changed"][0]
        judge.check("changed_row_is_alice",
                   before[0] == 1 and after[0] == 1,
                   f"expected the alice_j row (id 1); got before={before!r}")
        cols = ("id", "username", "email", "display_name", "summoner_name",
                "region", "password_hash", "joined_date")
        b, a = dict(zip(cols, before)), dict(zip(cols, after))
        judge.check("summoner_name_updated",
                   a["summoner_name"] == SUMMONER,
                   f"expected summoner_name={SUMMONER!r}; got {a['summoner_name']!r}")
        judge.check("region_updated", a["region"] == REGION,
                    f"expected region={REGION!r}; got {a['region']!r}")
        others = [k for k in cols if k not in ("summoner_name", "region") and b[k] != a[k]]
        judge.check("no_other_profile_fields_changed", not others,
                    f"unexpected collateral profile changes: {others!r}")
    check_only_tables_changed(judge, initial_db, after_db, {"users"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
