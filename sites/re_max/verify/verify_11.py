#!/usr/bin/env python3
"""verify_11.py — deterministic verifier for task REMAX--11.

Carol's account: remove non-Miami favorites; save a Miami condo <$400k search; report name + remaining count.

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
    check_trajectory_identity, contains_any_phrase, contains_count,
    entered_identity, favorites_of, final_answer, nav_favorites, nav_login,
    nav_srp, removed_rows, run_verifier, user_by_email)

TASK_ID = "REMAX--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: log-in + favorites + filtered Miami SRP + save-search
    judge.check("nav_login", nav_login(traj), "required: /login")
    judge.check("nav_favorites", nav_favorites(traj), "required: /favorites")
    judge.check("entered_carol_email", entered_identity(traj, "carol.d@test.com"),
                "required: login form filled with carol.d@test.com")
    judge.check("nav_miami_condo_srp",
                nav_srp(traj, "fl", "miami", home_type="Condo", price_max="400000"),
                "required: /fl/miami-real-estate with home_type=Condo, "
                "price_max=400000")
    # DB after-state: exactly Carol's two Naples favorites removed, her two
    # Miami favorites intact, exactly one saved search added, nothing else
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db,
                              ["favorites", "saved_searches"])
    gone = removed_rows(after_db, initial_db, "favorites", "id")
    judge.check("exactly_two_favorites_removed", len(gone) == 2,
                f"removed favorites: {gone}")
    if gone:
        judge.check("removed_are_naples",
                    sorted(g["listing_id"] for g in gone) == [121, 122],
                    f"removed ids: {[g['listing_id'] for g in gone]}")
    judge.check("carol_favorites_now",
                favorites_of(after_db, "carol.d@test.com") == [97, 98],
                f"carol favorites now: {favorites_of(after_db, 'carol.d@test.com')}")
    carol = user_by_email(after_db, "carol.d@test.com")
    new_searches = added_rows(after_db, initial_db, "saved_searches", "id")
    judge.check("exactly_one_saved_search", len(new_searches) == 1,
                f"new saved searches: {new_searches}")
    if new_searches:
        s = new_searches[0]
        judge.check("saved_search_owner", s["user_id"] == carol["id"],
                    f"user_id={s['user_id']}")
        judge.check("saved_search_name", s["name"] == "Miami, FL",
                    f"name={s['name']}")
        judge.check("saved_search_filters",
                    s["home_type"] == "Condo" and s["max_price"] == 400000
                    and s["city"] == "Miami" and s["state"] == "FL",
                    f"filters={dict(home_type=s['home_type'], max_price=s['max_price'])}")
    # ground truth (frozen seed): saved search named "Miami, FL"; 2 favorites remain
    judge.check("answer_saved_search_name",
                contains_any_phrase(answer, ["Miami, FL", "Miami FL"]),
                'must report the saved search name "Miami, FL"')
    judge.check("answer_remaining", contains_count(answer, 2),
                "must state 2 favorites remain")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
