#!/usr/bin/env python3
"""Verify Marriott--17.

New York City work trip 10/30/2026-11/01/2026, torn between The Lexington Hotel,
Autograph Collection and The Westin New York Grand Central: visit both hotels'
reviews pages and report each hotel's average rating, total review count, and
1-star review count; report which hotel has the lower share of 1-star reviews;
sign in as alice.j@test.com and save that hotel to the saved list; report the
confirmation message shown.

Frozen ground truth (seed DB): The Lexington (marsha NYCLX) — average 3.7,
4,354 reviews, 739 one-star (17.0% share); The Westin New York Grand Central
(marsha NYCZW) — average 3.9, 3,997 reviews, 509 one-star (12.7% share); the Westin
has the lower 1-star share and is the one to save; saving flashes
"The Westin New York Grand Central has been saved to your list.".
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_amount, contains_phrase, db_query,
                        final_answer, navigated_find_hotels, navigated_hotel_tab,
                        navigated_hotel_overview, run_verifier, table_delta)

TASK_ID = "Marriott--17"
LEX = ("The Lexington Hotel, Autograph Collection", "NYCLX", "the-lexington-hotel-autograph-collection",
       3.7, 4354, 739)
WES = ("The Westin New York Grand Central", "NYCZW", "the-westin-new-york-grand-central",
       3.9, 3997, 509)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_nyc_search", navigated_find_hotels(traj, "New York"),
                "required: /search/findHotels.mi with destinationAddress containing 'New York'")
    judge.check("visited_lex_reviews", navigated_hotel_tab(traj, "reviews", LEX[2]),
                "required: The Lexington reviews page")
    judge.check("visited_wes_reviews", navigated_hotel_tab(traj, "reviews", WES[2]),
                "required: The Westin New York Grand Central reviews page")
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("visited_wes_page_to_save", navigated_hotel_overview(traj, WES[2]),
                "required: The Westin New York Grand Central overview page (to save it)")
    # answer facts
    judge.check("answer_lex_avg", contains_amount(answer, LEX[3]),
                "expected Lexington average rating 3.7")
    judge.check("answer_lex_count", contains_amount(answer, LEX[4]),
                "expected Lexington review count 4,354")
    judge.check("answer_lex_one_star", contains_amount(answer, LEX[5]),
                "expected Lexington 1-star count 739")
    judge.check("answer_wes_avg", contains_amount(answer, WES[3]),
                "expected Westin average rating 3.9")
    judge.check("answer_wes_count", contains_amount(answer, WES[4]),
                "expected Westin review count 3,997")
    judge.check("answer_wes_one_star", contains_amount(answer, WES[5]),
                "expected Westin 1-star count 509")
    judge.check("answer_lower_share_verdict", contains_phrase(answer, "Westin New York Grand Central"),
                "the lower 1-star share belongs to The Westin New York Grand Central "
                "(509/3,997 = 12.7% vs 739/4,354 = 17.0%)")
    judge.check("answer_save_message",
                contains_phrase(answer, "The Westin New York Grand Central has been saved to your list."),
                "expected the exact save confirmation message")
    # DB after-state: exactly one favorite added (alice x The Westin — never another hotel)
    delta = table_delta(initial_db, after_db, "favorites")
    judge.check("one_favorite_added",
                len(delta["added"]) == 1 and len(delta["removed"]) == 0,
                f"expected exactly one added favorite; delta={delta!r}")
    westin_id = db_query(after_db, "SELECT id FROM hotels WHERE name = ?",
                         (WES[0],))
    alice_id = db_query(after_db, "SELECT id FROM users WHERE email = ?",
                        ("alice.j@test.com",))
    added_fav = db_query(after_db,
        "SELECT hotel_id FROM favorites WHERE user_id = ? AND saved_on = '2026-09-21'",
        (alice_id[0][0],)) if alice_id else []
    judge.check("added_favorite_is_the_westin",
                bool(westin_id) and bool(added_fav) and added_fav[0][0] == westin_id[0][0],
                f"expected the newly saved hotel to be {WES[0]} (id={westin_id and westin_id[0][0]}); "
                f"observed={added_fav!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("favorites",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
