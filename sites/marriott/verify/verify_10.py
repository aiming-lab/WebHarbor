#!/usr/bin/env python3
"""Verify Marriott--10.

Sign in as alice.j@test.com. From the saved hotels, remove the property located
in Austin; search New York City hotels and save The Times Square EDITION to the
list; sign out and sign back in; report the final names in the saved hotels list,
in the order shown.

Frozen ground truth (seed DB): alice's seed saved hotels = Aloft by Marriott
Austin Downtown (the Austin one), Moxy Atlanta Downtown, The Ritz-Carlton,
Atlanta; after the task the list = The Times Square EDITION (saved 2026-09-21,
sorted first), then Moxy Atlanta Downtown, then The Ritz-Carlton, Atlanta.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, final_answer,
                        input_texts, navigated_find_hotels, navigated_hotel_overview,
                        phrases_in_order, run_verifier, favorites_of, table_delta)

TASK_ID = "Marriott--10"
FINAL_ORDER = ["The Times Square EDITION", "Moxy Atlanta Downtown", "The Ritz-Carlton, Atlanta"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_saved_page", "/loyalty/myAccount/savedHotels.mi")
    judge.check("visited_nyc_search", navigated_find_hotels(traj, "New York"),
                "required: /search/findHotels.mi with destinationAddress containing 'New York'")
    judge.check("visited_edition_page", navigated_hotel_overview(traj, "the-times-square-edition"),
                "required: The Times Square EDITION overview page (to save it)")
    email_fills = input_texts(traj)
    judge.check("signed_out_and_back_in",
                email_fills.count("alice.j@test.com") >= 2
                and sum(1 for s in (traj.get("steps") or [])
                        if isinstance(s, dict) and "sign-in.mi" in str(s.get("url", ""))) >= 2,
                "required: the account signed in twice (sign out + sign back in): "
                f"email_fills={email_fills!r}")
    # answer: the three final names in the saved-list order
    judge.check("answer_final_names_in_order", phrases_in_order(answer, FINAL_ORDER),
                f"expected the final saved list in order: {' | '.join(FINAL_ORDER)}")
    # DB after-state: favorites = -Aloft Austin +The Times Square EDITION
    favs = favorites_of(after_db, "alice.j@test.com")
    names = [f["hotel_name"] for f in favs]
    judge.check("favorites_final_set", names == FINAL_ORDER,
                f"expected favorites {FINAL_ORDER!r}, observed={names!r}")
    delta = table_delta(initial_db, after_db, "favorites")
    judge.check("favorite_swap_delta", len(delta["added"]) == 1 and len(delta["removed"]) == 1,
                f"expected exactly one favorite added and one removed; delta={delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("favorites",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
