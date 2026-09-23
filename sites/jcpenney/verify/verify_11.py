#!/usr/bin/env python3
"""Verify JCPenney--11."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--11"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_shoes_sorted",
                navigated_to_path_with_params(traj, "/g/shoes/all-womens-shoes",
                                              {"sortBy": "price_low"}),
                "required: /g/shoes/all-womens-shoes with sortBy=price_low")
    judge.check("visited_tops_sorted",
                navigated_to_path_with_params(traj, "/g/women/tops",
                                              {"sortBy": "price_low"}),
                "required: /g/women/tops with sortBy=price_low")
    judge.check("visited_shorts_sorted",
                navigated_to_path_with_params(traj, "/g/women/shorts",
                                              {"sortBy": "price_low"}),
                "required: /g/women/shorts with sortBy=price_low")
    # Frozen ground truth (seed DB, live-sorted): women's shoes cheapest =
    # St. John's Bay Womens Hope Stacked Heel Booties at $27.99 (claim "From
    # $31.50" does not hold — the actual cheapest is lower); women's tees
    # cheapest = A.N.A Womens Crew Neck Long Sleeve T-Shirt at $9.09 (claim
    # "From $7.89" does not hold — no tee is priced that low); women's shorts
    # cheapest = A.N.A Patch Pocket Womens 4" Highest Rise Chino Short at $8.99
    # (claim "From $12.99" does not hold — the actual cheapest is lower).
    judge.check("answer_shoes_cheapest",
                contains_all(answer, ["Hope Stacked Heel Booties", "27.99"]),
                "expected the Hope Stacked Heel Booties at $27.99 as the cheapest women's shoe")
    judge.check("answer_tees_cheapest",
                contains_all(answer, ["Crew Neck Long Sleeve T-Shirt", "9.09"]),
                "expected the A.N.A Womens Crew Neck Long Sleeve T-Shirt at $9.09")
    judge.check("answer_shorts_cheapest",
                contains_all(answer, ["Chino Short", "8.99"]),
                "expected the A.N.A Patch Pocket 4\" Chino Short at $8.99")
    judge.check("answer_claims_restated",
                contains_all(answer, ["31.50", "7.89", "12.99"]),
                "expected the three claim values (31.50 / 7.89 / 12.99) restated")
    judge.check("answer_verdicts_negative",
                contains_any(answer, ["does not hold", "doesn't hold", "not hold", "false",
                                      "does not match", "doesn't match", "not true",
                                      "not accurate", "incorrect"]),
                "expected the verdict that the homepage claims do not hold")
    judge.check("answer_shoes_claim_pairing",
                fact_owner(answer, "31.50", ("shoes", "shoe"), ("tees", "tee", "shorts", "short"))
                and fact_owner(answer, "27.99", ("shoes", "shoe"),
                               ("tees", "tee", "shorts", "short")),
                "expected the shoes claim (31.50) and actual price (27.99) attributed to shoes")
    judge.check("answer_tees_claim_pairing",
                fact_owner(answer, "7.89", ("tees", "tee"), ("shoes", "shoe", "shorts", "short"))
                and fact_owner(answer, "9.09", ("tees", "tee"),
                               ("shoes", "shoe", "shorts", "short")),
                "expected the tees claim (7.89) and actual price (9.09) attributed to tees")
    judge.check("answer_shorts_claim_pairing",
                fact_owner(answer, "12.99", ("shorts", "short"), ("shoes", "shoe", "tees", "tee"))
                and fact_owner(answer, "8.99", ("shorts", "short"),
                               ("shoes", "shoe", "tees", "tee")),
                "expected the shorts claim (12.99) and actual price (8.99) attributed to shorts")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
