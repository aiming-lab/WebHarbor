#!/usr/bin/env python3
"""Verify LandWatch--14 — custom search profiles on the main Land for Sale page.

Ground truth (frozen seed): with the custom price range $100,000 - $250,000
on /land (priceMin=100000&priceMax=250000), 38 listings match, the first
being 'Beautiful Live Water Property' at $209,800 in Williamson County, and
the Sale Type filter group counts 38 For Sale and 0 Auction within the
budget. With the price range cleared and the custom size range 100 - 200
acres (acresMin=100&acresMax=200), 71 listings match, the first being
'Gaddistown on the Toccoa' at $6,500,000.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, navigated_to,
                        run_verifier)

TASK_ID = "LandWatch--14"
LAND = "/land"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_land_page", LAND)
    # navigation gates: both custom-range searches were actually submitted
    judge.check("used_custom_price_range",
                navigated_to(traj, "priceMin=") and navigated_to(traj, "priceMax="),
                "expected priceMin/priceMax query params from the custom price form")
    judge.check("used_custom_size_range",
                navigated_to(traj, "acresMin=") and navigated_to(traj, "acresMax="),
                "expected acresMin/acresMax query params from the custom size form")
    # budget leg: $100,000 - $250,000
    judge.check("answer_budget_total", contains_count(answer, 38),
                "expected 38 listings in the $100,000 - $250,000 budget")
    judge.check("answer_budget_first_title",
                contains_phrase(answer, "Beautiful Live Water Property"),
                "expected the first listing 'Beautiful Live Water Property'")
    judge.check("answer_budget_first_price", contains_money(answer, 209800),
                "expected the first listing at $209,800")
    judge.check("answer_budget_first_county", contains_phrase(answer, "Williamson"),
                "expected Williamson County for the first listing")
    judge.check("answer_sale_type_for_sale_count",
                contains_phrase(answer, "For Sale") and contains_count(answer, 38),
                "expected the For Sale facet count 38 within the budget")
    judge.check("answer_sale_type_auction_count",
                contains_phrase(answer, "Auction") and contains_count(answer, 0),
                "expected the Auction facet count 0 within the budget")
    # size leg: 100 - 200 acres
    judge.check("answer_size_total", contains_count(answer, 71),
                "expected 71 listings in the 100 - 200 acre range")
    judge.check("answer_size_first_title",
                contains_phrase(answer, "Gaddistown on the Toccoa"),
                "expected the first listing 'Gaddistown on the Toccoa'")
    judge.check("answer_size_first_price", contains_money(answer, 6500000),
                "expected the first listing at $6,500,000")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
