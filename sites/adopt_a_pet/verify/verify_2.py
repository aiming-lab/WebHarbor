#!/usr/bin/env python3
"""Verify AdoptAPet--2: location "Phoenix, AZ" + male dogs -> lowest adoption fee across ALL
matching profiles (7 dogs on two results pages): Batman, Chihuahua / Yorkshire Terrier, $165.

The mirror scores location by token overlap, so "Phoenix, AZ" returns every Arizona pet;
fees are only on detail pages, so all seven profiles and results page 2 are required.
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

TASK_ID = "AdoptAPet--2"
CANDIDATES = [p["slug"] for p in GT.search("Phoenix, AZ", "Dog", sex="Male")]  # 7 male AZ dogs
WINNER = GT.pet("batman")
OTHERS = [GT.pet(s)["name"] for s in CANDIDATES if s != WINNER["slug"]]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("candidate_set_is_seven", len(CANDIDATES) == 7 and min(GT.pet(s)["fee"] for s in CANDIDATES) == WINNER["fee"],
                f"candidates={CANDIDATES!r}")
    check_search_visited(judge, traj, "visited_male_dog_search_statewide_az",
                         location_any=AZ_WIDE, species="Dog", sex="Male")
    check_search_visited(judge, traj, "visited_results_page_2",
                         location_any=AZ_WIDE, species="Dog", sex="Male", page="2")
    check_visited_pets(judge, traj, CANDIDATES)
    judge.check("answer_names_winner", contains_all(answer, [WINNER["name"]]), f"expected={WINNER['name']!r}, answer={answer!r}")
    judge.check("answer_has_both_breeds", contains_all(answer, GT.breeds(WINNER)),
                f"expected={GT.breeds(WINNER)!r}, answer={answer!r}")
    judge.check("answer_has_fee", contains_money(answer, WINNER["fee"]), f"expected=${WINNER['fee']}, answer={answer!r}")
    judge.check("answer_identifies_lowest_fee_pet", identifies(answer, WINNER["name"], OTHERS, LOWEST, HIGHEST),
                f"winner={WINNER['name']!r}, others={OTHERS!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
