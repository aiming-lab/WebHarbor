#!/usr/bin/env python3
"""Verify AdoptAPet--12: small dogs near Arizona -> youngest of five: Batman, 36 months,
Chihuahua / Yorkshire Terrier, Tucson (read-only).

Cards show only the age GROUP; two candidates are Seniors (older by definition), the three
Adults (Batman 36, Winston 60, Zorro 72 months) must all be opened to find the youngest.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    AZ_WIDE, OLDEST, YOUNGEST, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pets, contains_all, contains_months, final_answer, identifies, run_verifier,
)

TASK_ID = "AdoptAPet--12"
CANDIDATES = [p["slug"] for p in GT.search("Arizona", "Dog", size="Small")]  # 5 small AZ dogs
MUST_OPEN = [s for s in CANDIDATES if GT.pet(s)["age_group"] == "Adult"]  # batman, winston, zorro
WINNER = GT.pet("batman")
OTHERS = [GT.pet(s)["name"] for s in CANDIDATES if s != WINNER["slug"]]


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    judge.check("candidate_set_is_five", len(CANDIDATES) == 5 and min(GT.pet(s)["age_months"] for s in CANDIDATES) == WINNER["age_months"],
                f"candidates={CANDIDATES!r}")
    check_search_visited(judge, traj, "visited_small_dog_search_arizona", location_any=AZ_WIDE, species="Dog", size="Small")
    check_visited_pets(judge, traj, MUST_OPEN)
    judge.check("answer_names_winner", contains_all(answer, [WINNER["name"]]), f"expected={WINNER['name']!r}, answer={answer!r}")
    judge.check("answer_has_age_months", contains_months(answer, WINNER["age_months"]), f"expected={WINNER['age_months']} months, answer={answer!r}")
    judge.check("answer_has_both_breeds", contains_all(answer, GT.breeds(WINNER)), f"expected={GT.breeds(WINNER)!r}, answer={answer!r}")
    judge.check("answer_has_city", contains_all(answer, [WINNER["city"]]), f"expected={WINNER['city']!r}, answer={answer!r}")
    judge.check("answer_identifies_youngest", identifies(answer, WINNER["name"], OTHERS, YOUNGEST, OLDEST),
                f"winner={WINNER['name']!r}, others={OTHERS!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
