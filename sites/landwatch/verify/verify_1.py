#!/usr/bin/env python3
"""Verify LandWatch--1 — Texas land + $1,000,000-and-up price filter + Price: Low to High sort.

Ground truth (frozen seed): 81 Texas listings at $1M+; the cheapest is
'East Texas Poultry Farm LOCATED NEAR COOKVILLE TEXAS' at $1,050,000 in
Titus County.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--1"
FILTER_PATH = "/texas-land-for-sale/price-over-1000000"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_texas_land_page", "/texas-land-for-sale")
    check_visited_path(judge, traj, "visited_1m_price_filter_page", FILTER_PATH)
    judge.check("visited_price_low_sort", any("sort=price-low" in u for u in
                [s.get("url", "") + s.get("url_after", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected ?sort=price-low on the filtered page")
    judge.check("answer_total_listings", contains_count(answer, 81),
                "expected 81 listings in the results heading")
    judge.check("answer_cheapest_title", contains_phrase(answer, "East Texas Poultry Farm"),
                "expected the cheapest listing 'East Texas Poultry Farm LOCATED NEAR COOKVILLE TEXAS'")
    judge.check("answer_cheapest_title_tail", contains_phrase(answer, "LOCATED NEAR COOKVILLE TEXAS"),
                "expected the cheapest listing title tail 'LOCATED NEAR COOKVILLE TEXAS'")
    judge.check("answer_cheapest_price", contains_money(answer, 1050000),
                "expected the cheapest listing price $1,050,000")
    judge.check("answer_cheapest_county", contains_phrase(answer, "Titus County"),
                "expected Titus County")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
