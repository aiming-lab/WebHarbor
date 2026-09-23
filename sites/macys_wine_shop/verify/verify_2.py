#!/usr/bin/env python3
"""Verify MacysWineShop--2: all-wine collection, Cabernet Sauvignon facet, price sort"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--2"

KELHAM_PDFS = ["/products/kelham-cabernet-sauvignon-oakville-ava-napa-california-2025",
                "/products/kelham-cabernet-sauvignon-oakville-ava-napa-california-2026",
                "/products/kelham-cabernet-sauvignon-oakville-ava-napa-california-2024",
                "/products/kelham-cabernet-sauvignon-oakville-ava-napa-california-2023"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_all_wine_with_cabernet_facet",
                navigated_collection_with_facets(traj, "all-wine", {"varietal": "Cabernet Sauvignon"}),
                "required: /collections/all-wine?filter.p.m.drinks.varietal=Cabernet+Sauvignon")
    judge.check("collection_sorted_price_ascending",
                navigated_listing_sorted(traj, "/collections/all-wine", "price-ascending"),
                "required: sort_by=price-ascending on the filtered collection")
    judge.check("opened_most_expensive_product_page",
                navigated_to_path_any(traj, KELHAM_PDFS) or navigated_to(traj, "/products/kelham"),
                "required: the most expensive wine's product page (Kelham Cabernet Sauvignon)")
    # Frozen ground truth: 19 wines; cheapest 2022 Della Flora Organic Cabernet
    # Sauvignon $16.99; the most expensive (Kelham ... 2011, $195.00) is from the United States.
    judge.check("answer_filtered_count", contains_count(answer, 19),
                "expected 19 wines in the filtered list")
    judge.check("answer_cheapest", contains_phrase(answer, "Della Flora Organic Cabernet Sauvignon")
                and contains_money(answer, 16.99),
                "expected cheapest '2022 Della Flora Organic Cabernet Sauvignon' at $16.99")
    judge.check("answer_most_expensive_country", contains_phrase(answer, "United States"),
                "expected the most expensive wine's country: United States")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
