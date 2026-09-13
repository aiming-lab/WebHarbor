#!/usr/bin/env python3
"""Verify AdoptAPet--3: adult cats near Arizona, house-trained + good with cats, lowest fee ->
Cinders, Sedona, Domestic Shorthair, $120 (read-only). Both adult AZ cats qualify, so both
detail pages are required to compare fees.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    AZ_WIDE, HIGHEST, LOWEST, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pets, contains_all, contains_money, final_answer, identifies, run_verifier,
)

TASK_ID = "AdoptAPet--3"
CANDIDATES = [p["slug"] for p in GT.search("Arizona", "Cat", age="Adult")]  # casper, cinders
WINNER = GT.pet("cinders")
OTHERS = [GT.pet(s)["name"] for s in CANDIDATES if s != WINNER["slug"]]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("candidate_set_is_two_qualifying", len(CANDIDATES) == 2 and all(
        GT.pet(s)["house_trained"] and GT.pet(s)["good_cats"] for s in CANDIDATES), f"candidates={CANDIDATES!r}")
    check_search_visited(judge, traj, "visited_adult_cat_search_arizona", location_any=AZ_WIDE, species="Cat", age="Adult")
    check_visited_pets(judge, traj, CANDIDATES)
    judge.check("answer_names_winner", contains_all(answer, [WINNER["name"]]), f"expected={WINNER['name']!r}, answer={answer!r}")
    judge.check("answer_has_city", contains_all(answer, [WINNER["city"]]), f"expected={WINNER['city']!r}, answer={answer!r}")
    judge.check("answer_has_breed", contains_all(answer, [WINNER["breed"]]), f"expected={WINNER['breed']!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, WINNER["fee"]), f"expected=${WINNER['fee']}, answer={answer!r}")
    judge.check("answer_identifies_lowest_fee_pet", identifies(answer, WINNER["name"], OTHERS, LOWEST, HIGHEST),
                f"winner={WINNER['name']!r}, others={OTHERS!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
