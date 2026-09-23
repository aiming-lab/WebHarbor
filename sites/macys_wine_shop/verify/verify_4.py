#!/usr/bin/env python3
"""Verify MacysWineShop--4: Italy + Sweet facet combination"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--4"

MATCHING = [
    ("Abbazia Moscato Vino Dolce", 16.99),
    ("Abbazia La Tartaruga Moscato", 12.59),
    ("Tesoro Vite Sparkling Moscato", 17.99),
    ("Abbazia Moscato Dolce", 16.99),
    ("Tesoro Vite Sparkling Wine Moscato", 15.99),
    ("Abbazia Sparkling Moscato Rose Dolce", 16.99),
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_all_wine_with_italy_sweet_facets",
                navigated_collection_with_facets(traj, "all-wine",
                                                 {"country": "Italy", "sweetness": "Sweet"}),
                "required: /collections/all-wine?filter.p.m.drinks.country=Italy&filter.p.m.drinks.sweetness=Sweet")
    # Frozen ground truth: 6 matching wines.
    judge.check("answer_match_count", contains_count(answer, 6),
                "expected 6 matching wines")
    for name, price in MATCHING:
        judge.check(f"answer_lists_{name[:24].replace(' ', '_').lower()}",
                    contains_phrase(answer, name) and contains_money(answer, price),
                    f"expected '{name}' at ${price:.2f}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
