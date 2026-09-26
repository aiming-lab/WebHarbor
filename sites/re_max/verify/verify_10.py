#!/usr/bin/env python3
"""verify_10.py — deterministic verifier for task REMAX--10.

Bob removes his most expensive favorite and his Denver saved search, then
finds the cheapest Austin home with a Saturday open house and saves it.
Report the final favorite count, the new most expensive favorite's price,
and the remaining saved-search count.

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
    check_trajectory_identity, contains_amount, contains_count,
    entered_identity, favorites_of, final_answer, nav_account, nav_favorites,
    nav_ldp, nav_login, nav_srp, removed_rows, rows_of, run_verifier)

TASK_ID = "REMAX--10"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: log-in + favorites + account (saved searches) + the
    # Austin open-house SRP + the chosen home's detail page
    judge.check("nav_login", nav_login(traj), "required: /login")
    judge.check("nav_favorites", nav_favorites(traj), "required: /favorites")
    judge.check("nav_account", nav_account(traj), "required: /account (saved searches)")
    judge.check("entered_bob_email", entered_identity(traj, "bob.c@test.com"),
                "required: login form filled with bob.c@test.com")
    judge.check("nav_austin_open_house_srp",
                nav_srp(traj, "tx", "austin", open_house="1"),
                "required: /tx/austin-real-estate with open_house=1")
    judge.check("nav_ldp_8525_birmingham", nav_ldp(traj, 279),
                "required: listing detail for 8525 Birmingham Dr (id 279)")
    # DB after-state: Bob's favorite 264 (2707 E Side Dr) removed, favorite
    # 279 (8525 Birmingham Dr) added, his "Denver townhouses" saved search
    # removed, nothing else changed
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db,
                               ["favorites", "saved_searches"])
    gone = removed_rows(after_db, initial_db, "favorites", "id")
    judge.check("exactly_one_favorite_removed", len(gone) == 1,
                f"removed favorites: {gone}")
    if gone:
        judge.check("removed_is_2707_e_side", gone[0]["listing_id"] == 264,
                    f"removed listing_id={gone[0]['listing_id']} (expected 264)")
    added = added_rows(after_db, initial_db, "favorites", "id")
    judge.check("exactly_one_favorite_added", len(added) == 1,
                f"added favorites: {added}")
    if added:
        judge.check("added_is_8525_birmingham", added[0]["listing_id"] == 279,
                    f"added listing_id={added[0]['listing_id']} (expected 279)")
    judge.check("bob_favorites_now",
                favorites_of(after_db, "bob.c@test.com") == [265, 266, 267, 279],
                f"bob favorites now: {favorites_of(after_db, 'bob.c@test.com')}")
    ss_gone = removed_rows(after_db, initial_db, "saved_searches", "id")
    judge.check("exactly_one_search_removed", len(ss_gone) == 1,
                f"removed searches: {ss_gone}")
    if ss_gone:
        judge.check("removed_is_denver_search",
                   (ss_gone[0]["name"] or "").lower().startswith("denver"),
                   f"removed search name={ss_gone[0]['name']}")
    bob_ss_after = [r for r in rows_of(after_db, "saved_searches")
                    if r["user_id"] == 2]
    judge.check("bob_searches_now", len(bob_ss_after) == 1,
                f"bob saved searches now: {bob_ss_after}")
    # ground truth (frozen seed): 4 favorites remain; new most expensive
    # $799,990 (11622 Doyle Overton Rd); 1 saved search remains
    judge.check("answer_remaining", contains_count(answer, 4),
                "must state 4 favorites remain")
    judge.check("answer_new_max", contains_amount(answer, 799990),
                "must quote the new most expensive favorite $799,990")
    judge.check("answer_searches_remaining", contains_count(answer, 1),
                "must state 1 saved search remains")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
