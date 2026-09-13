#!/usr/bin/env python3
"""Verify AdoptAPet--19: dogs near Arizona -> among the profiles marked good with children,
the lowest adoption fee: Arno, Casa Grande, German Shepherd Dog / Mixed Breed, 43 months,
$200 (read-only).

Eight Arizona dogs span two results pages; "good with children" and the fee are only on the
profile pages, so every one of the eight profiles and results page 2 are required.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    AZ_WIDE, HIGHEST, LOWEST, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pets, contains_all, contains_money, contains_months, final_answer, identifies, run_verifier,
)

TASK_ID = "AdoptAPet--19"
CANDIDATES = [p["slug"] for p in GT.search("Arizona", "Dog")]  # 8 AZ dogs
QUALIFYING = [s for s in CANDIDATES if GT.pet(s)["good_children"]]  # arno, horus, waymo, yuki
WINNER = GT.pet("arno")
OTHERS = [GT.pet(s)["name"] for s in CANDIDATES if s != WINNER["slug"]]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("candidate_set_is_eight_with_four_qualifying",
                len(CANDIDATES) == 8 and len(QUALIFYING) == 4 and min(GT.pet(s)["fee"] for s in QUALIFYING) == WINNER["fee"],
                f"candidates={CANDIDATES!r}, qualifying={QUALIFYING!r}")
    check_search_visited(judge, traj, "visited_dog_search_arizona", location_any=AZ_WIDE, species="Dog")
    check_search_visited(judge, traj, "visited_results_page_2", location_any=AZ_WIDE, species="Dog", page="2")
    check_visited_pets(judge, traj, CANDIDATES)
    judge.check("answer_names_winner", contains_all(answer, [WINNER["name"]]), f"expected={WINNER['name']!r}, answer={answer!r}")
    judge.check("answer_has_city", contains_all(answer, [WINNER["city"]]), f"expected={WINNER['city']!r}, answer={answer!r}")
    judge.check("answer_has_both_breeds", contains_all(answer, GT.breeds(WINNER)), f"expected={GT.breeds(WINNER)!r}, answer={answer!r}")
    judge.check("answer_has_age_months", contains_months(answer, WINNER["age_months"]), f"expected={WINNER['age_months']} months, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, WINNER["fee"]), f"expected=${WINNER['fee']}, answer={answer!r}")
    judge.check("answer_identifies_lowest_fee_pet", identifies(answer, WINNER["name"], OTHERS, LOWEST, HIGHEST),
                f"winner={WINNER['name']!r}, others={OTHERS!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
