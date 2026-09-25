#!/usr/bin/env python3
"""Sign in as alice.j@test.com (password TestPass123!). I've changed my travel plans from Austin to New York. Replace the Austin property on my saved hotels list with The Times Square EDITION, keeping my other saved hotels. Tell me which hotels are on my updated list."""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, final_answer,
                        input_texts, navigated_find_hotels, navigated_hotel_overview,
                        contains_phrase, phrases_in_order, run_verifier, favorites_of, table_delta)

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
    # answer: the three final names in the saved-list order
    judge.check("answer_final_names_in_order", all(contains_phrase(answer, name) for name in FINAL_ORDER),
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
