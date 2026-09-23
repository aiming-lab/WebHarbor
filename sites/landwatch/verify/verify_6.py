#!/usr/bin/env python3
"""Verify LandWatch--6 — Houston Region results via the Texas Region Map filter.

Ground truth (frozen seed): the Houston Region page shows 5 listings; the
first is 'Kountze Countryside Retreat' at $510,600 for 74 Acres.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_count,
                        contains_money, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "LandWatch--6"
REGION_PATH = "/texas-land-for-sale/houston-region"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_texas_land_page", "/texas-land-for-sale")
    check_visited_path(judge, traj, "visited_houston_region_page", REGION_PATH)
    judge.check("answer_region_total", contains_count(answer, 5),
                "expected 5 listings on the Houston Region page")
    judge.check("answer_first_title", contains_phrase(answer, "Kountze Countryside Retreat"),
                "expected the first listing 'Kountze Countryside Retreat'")
    judge.check("answer_first_price", contains_money(answer, 510600),
                "expected the first listing price $510,600")
    judge.check("answer_first_acres", contains_acres(answer, 74),
                "expected the first listing acreage 74 Acres")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
