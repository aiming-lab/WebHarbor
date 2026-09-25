#!/usr/bin/env python3
"""Verify JCPenney--12."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--12"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    HOPE = "/p/st-john-s-bay-womens-hope-stacked-heel-booties/ppr5008660553"
    judge.check("visited_gallery_price_low",
                navigated_to_path_with_params(traj, "/g/shoes/all-womens-shoes",
                                              {"sortBy": "price_low"}),
                "required: /g/shoes/all-womens-shoes with sortBy=price_low")
    judge.check("visited_gallery_price_high",
                navigated_to_path_with_params(traj, "/g/shoes/all-womens-shoes",
                                              {"sortBy": "price_high"}),
                "required: /g/shoes/all-womens-shoes with sortBy=price_high")
    judge.check("visited_gallery_top_rated",
                navigated_to_path_with_params(traj, "/g/shoes/all-womens-shoes",
                                              {"sortBy": "rating"}),
                "required: /g/shoes/all-womens-shoes with sortBy=rating (Top Rated)")
    check_visited_path(judge, traj, "visited_best_rated_pdp", HOPE)
    # Frozen ground truth (seed DB, 7 women's shoes): cheapest = St. John's Bay
    # Womens Hope Stacked Heel Booties $27.99 (tie with the Kinnel booties at the
    # same price; the low sort lists Hope first); most expensive = Liz Claiborne
    # Womens Thane Block Heel Riding Boots $48.99; Top Rated = the same Hope
    # booties (5.0 stars, 2 reviews) — the best-rated shoe is also the cheapest;
    # most reviews = Liz Claiborne Inca Womens Suede Loafers (3.8 stars shown,
    # 8 reviews); the Hope booties' rating breakdown: 5 stars 2, 1 star 0.
    judge.check("answer_cheapest_shoe",
                contains_all(answer, ["Hope Stacked Heel Booties", "27.99"]),
                "expected the Hope Stacked Heel Booties at $27.99 as the cheapest")
    judge.check("answer_most_expensive_shoe",
                contains_all(answer, ["Thane Block Heel Riding Boots", "48.99"]),
                "expected the Thane Block Heel Riding Boots at $48.99 as the most expensive")
    judge.check("answer_best_rated_shoe",
                contains_all(answer, ["Hope Stacked Heel Booties", "5.0"]) and
                contains_count(answer, 2),
                "expected the Hope booties as best rated (5.0 stars, 2 reviews)")
    judge.check("answer_most_reviewed_shoe",
                contains_all(answer, ["Inca", "3.8"]) and contains_count(answer, 8),
                "expected the Inca Suede Loafers (3.8 stars shown, 8 reviews) as most reviewed")
    judge.check("answer_breakdown_five_star",
                bool(_re.search(r"5\s*stars?\D{0,14}\b2\b", answer, _re.I)),
                "expected the 5-star count 2 in the breakdown")
    judge.check("answer_breakdown_one_star",
                bool(_re.search(r"1\s*stars?\D{0,14}\b0\b", answer, _re.I)),
                "expected the 1-star count 0 in the breakdown")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
