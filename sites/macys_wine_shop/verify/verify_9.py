#!/usr/bin/env python3
"""Verify MacysWineShop--9: Casa de Alqueria Reserva Red Blend award + wine info"""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, changed_tables, contains_all,
                        contains_any, contains_count, contains_free, contains_money, contains_percent,
                        contains_phrase, entered_identity, final_answer, input_texts,
                        navigated_collection_with_facets, navigated_listing_sorted, navigated_search_with, navigated_to,
                        navigated_to_path, navigated_to_path_any, phrases_in_order, run_verifier,
                        table_delta, db_query, cart_rows, orders_of, order_items_of)

TASK_ID = "MacysWineShop--9"

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_casa_product_page",
                       "/products/2024-casa-de-alqueria-reserva-red-blend-chile")
    # Frozen ground truth: Gold, 2026, Critics Challenge International Wine
    # Competition; ABV 13.5; region Valle Central.
    judge.check("answer_award_level", contains_phrase(answer, "Gold"),
                "expected the Gold medal level")
    judge.check("answer_award_year", contains_count(answer, 2026),
                "expected the 2026 award year")
    judge.check("answer_award_competition",
                contains_phrase(answer, "Critics Challenge International Wine Competition"),
                "expected the Critics Challenge International Wine Competition")
    judge.check("answer_abv", contains_phrase(answer, "13.5"),
                "expected ABV 13.5")
    judge.check("answer_region", contains_phrase(answer, "Valle Central"),
                "expected region Valle Central")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
