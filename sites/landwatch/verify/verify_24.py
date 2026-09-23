#!/usr/bin/env python3
"""Verify LandWatch--24 — Undeveloped Land + $50,000 - $99,999 price filter + Price: Low to High.

Ground truth (frozen seed): 3 listings; the cheapest is 'Jaz Meadows 2-Acre
Homesites' at $77,500 in Navarro County.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--24"
FILTER_PATH = "/undeveloped-land/price-50000-99999"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_undeveloped_page", "/undeveloped-land")
    check_visited_path(judge, traj, "visited_price_filter_page", FILTER_PATH)
    judge.check("visited_price_low_sort", any("sort=price-low" in u for u in
                [s.get("url", "") + s.get("url_after", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected ?sort=price-low on the filtered page")
    judge.check("answer_total_listings", contains_count(answer, 3),
                "expected 3 listings in the results heading")
    judge.check("answer_cheapest_title", contains_phrase(answer, "Jaz Meadows 2-Acre Homesites"),
                "expected the cheapest listing 'Jaz Meadows 2-Acre Homesites'")
    judge.check("answer_cheapest_price", contains_money(answer, 77500),
                "expected the cheapest listing price $77,500")
    judge.check("answer_cheapest_county", contains_phrase(answer, "Navarro County"),
                "expected Navarro County")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
