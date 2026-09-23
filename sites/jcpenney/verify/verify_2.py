#!/usr/bin/env python3
"""Verify JCPenney--2."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, run_verifier, stable_password_hash)

TASK_ID = "JCPenney--2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_bedding_with_liz_claiborne_filter",
                 navigated_listing_with_filter(traj, "/g/home-store/all-bedding", "brand", "liz claiborne"),
                 "required: /g/home-store/all-bedding?brand=liz+claiborne")
    # Frozen ground truth (seed DB, bedding category x LIZ CLAIBORNE brand facet):
    # 2 products — Luxury Performance 1000tc ($41.99 - $200.00) and Ultra Fit
    # Performance 575TC ($34.99 - $180.00).
    judge.check("answer_brand_product_count", contains_count(answer, 2),
                "expected 2 LIZ CLAIBORNE bedding products")
    judge.check("answer_first_product", contains_phrase(answer, "Luxury Performance 1000tc Sheet Set"),
                "expected Liz Claiborne Luxury Performance 1000tc Sheet Set")
    judge.check("answer_second_product", contains_phrase(answer, "Ultra Fit Performance 575TC Sheet Set"),
                "expected Liz Claiborne Ultra Fit Performance 575TC Sheet Set")
    judge.check("answer_most_expensive_range", contains_money(answer, [41.99, 200.00]),
                "expected the most expensive one's price range $41.99 - $200.00")
    # the most-expensive CLAIM itself must identify the 1000tc product (not the
    # cheaper 575TC), so a swapped attribution cannot pass by listing both ranges
    import re as _re
    m = _re.search(r"most expensive", answer, _re.I)
    tail = answer[m.end():] if m else ""
    judge.check("answer_most_expensive_identity",
                bool(m) and "1000tc" in tail.lower() and contains_money(tail, [41.99, 200.00]),
                "the text after 'most expensive' must name the Luxury Performance 1000tc "
                "sheet set with the $41.99 - $200.00 range")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
