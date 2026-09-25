#!/usr/bin/env python3
"""Verify League of Legends--11: new-user onboarding (signup -> profile -> writes ->
sign out -> sign in -> persistence).

Honest chain (~26 atomic actions): Play Now -> fill username -> fill email ->
fill display name -> fill password -> Create Account -> Edit Profile -> fill
summoner 'HarborRookie' -> select EUW -> Save Changes -> Champions nav -> fill
q='Milio' -> Apply -> open Milio -> Add to Favorites -> Patch Notes nav ->
open 26.19 -> Save Article -> My Account -> Sign Out -> Play Now -> Sign In
link -> fill email -> fill password -> submit -> answer (persisted profile read
on the account page).

Frozen ground truth (seed DB):
  * A fresh signup starts with 0 favorites and 0 bookmarks; after the chain it
    has exactly 1 favorite (Milio, champion id 84) and 1 bookmark
    ('League of Legends Patch 26.19 Notes', article id 133).
  * The profile edit must leave summoner_name='HarborRookie' and region='EUW'
    (joined_date pinned '2026-09-22' by the mirror).
  * Database delta: exactly one new users row (id 5, fresh username/email),
    one favorite_champions row and one bookmark_articles row for that user.
"""
from verify_lib import (bound_phrase, check_only_tables_changed,
                        check_trajectory_identity, contains_count,
                        contains_phrase, entered_identity, fav_triples, bm_triples,
                        final_answer, navigated_champion, navigated_to_path,
                        run_verifier, SEED_USERS, table_delta)

TASK_ID = "League of Legends--11"
MILIO = (5, 84, "2026-09-22")
PATCH_2619_BM = (5, 133, "2026-09-22")
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_signup", navigated_to_path(traj, "/signup"),
                "required: /signup (account creation)")
    judge.check("visited_profile_edit", navigated_to_path(traj, "/account/profile"),
                "required: /account/profile (summoner/region completion)")
    judge.check("visited_milio_page", navigated_champion(traj, "milio"),
                "required: /champions/milio/")
    judge.check("visited_patch_2619", navigated_to_path(traj, PATCH_2619),
                f"required: {PATCH_2619}")
    judge.check("visited_relogin", navigated_to_path(traj, "/login"),
                "required: /login (sign in again after sign out)")
    judge.check("visited_account", navigated_to_path(traj, "/account"),
                "required: /account")
    judge.check("entered_rookie_summoner", entered_identity(traj, "HarborRookie"),
                "expected 'HarborRookie' in an input step")

    judge.check("answer_summoner_name",
                bound_phrase(answer, "HarborRookie", "summoner", ["region"], mode="after",
                             optional_owner=True),
                "expected the summoner name 'HarborRookie' attached to the summoner field")
    judge.check("answer_region_euw",
                bound_phrase(answer, "EUW", "region", ["summoner"], mode="after",
                             optional_owner=True),
                "expected the region EUW attached to the region field")
    judge.check("answer_favorites_total_1", contains_count(answer, 1),
                "expected 1 favorite champion reported")
    judge.check("answer_saved_total_1", contains_phrase(answer, "1 saved") or
                contains_phrase(answer, "saved article"),
                "expected 1 saved article reported")

    users_delta = table_delta(initial_db, after_db, "users")
    added = users_delta["added"]
    ok_added = len(added) == 1
    row = None
    if ok_added:
        # sqlite column order: id, username, email, display_name, summoner_name,
        # region, password_hash, joined_date
        row = dict(zip(["id", "username", "email", "display_name", "summoner_name",
                        "region", "password_hash", "joined_date"], added[0]))
        ok_added = (row["summoner_name"] == "HarborRookie" and row["region"] == "EUW"
                    and row["joined_date"] == "2026-09-22"
                    and row["email"] not in {e for e in SEED_USERS}
                    and row["username"] not in {u[1] for u in SEED_USERS.values()})
    judge.check("users_delta_single_new_row", ok_added and not users_delta["removed"]
                and not users_delta["changed"],
                f"expected exactly one new user row (HarborRookie/EUW); observed={row!r}")

    new_user_id = row["id"] if ok_added else None
    favs_ok = new_user_id is not None and fav_triples(after_db) == \
        sorted(set(fav_triples(initial_db)) | {(new_user_id, 84, "2026-09-22")})
    judge.check("favorites_delta_new_user_milio", favs_ok,
                f"expected exactly one favorite row (new user {new_user_id}, Milio)")
    bms_ok = new_user_id is not None and bm_triples(after_db) == \
        sorted(set(bm_triples(initial_db)) | {(new_user_id, 133, "2026-09-22")})
    judge.check("bookmarks_delta_new_user_patch2619", bms_ok,
                "expected exactly one bookmark row (new user, Patch 26.19 Notes)")
    check_only_tables_changed(judge, initial_db, after_db,
                              {"users", "favorite_champions", "bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
