#!/usr/bin/env python3
"""Verify AdoptAPet--5: pets near Seattle, WA -> Daisy vs Pepper: species, age in months,
fee, and which has the lower fee (Pepper) (read-only).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ground_truth as GT  # noqa: E402
from verify_lib import (  # noqa: E402
    HIGHEST, LOWEST, Judge, check_read_only, check_search_visited, check_trajectory_identity,
    check_visited_pets, contains_all, contains_money, contains_months, final_answer, identifies, run_verifier,
)

TASK_ID = "AdoptAPet--5"
DAISY, PEPPER = GT.pet("daisy"), GT.pet("pepper")  # Dog 30 mo $275 / Cat 13 mo $130


def run_checks(judge: Judge, traj: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, traj, TASK_ID)
    answer = final_answer(traj)
    check_search_visited(judge, traj, "visited_search_near_seattle", location_any=({"seattle"}, {"wa"}, {"washington"}))
    check_visited_pets(judge, traj, [DAISY["slug"], PEPPER["slug"]])
    judge.check("answer_names_both_pets", contains_all(answer, [DAISY["name"], PEPPER["name"]]), f"answer={answer!r}")
    judge.check("answer_has_both_species", contains_all(answer, [DAISY["species"], PEPPER["species"]]),
                f"expected={[DAISY['species'], PEPPER['species']]!r}, answer={answer!r}")
    judge.check("answer_has_both_ages", contains_months(answer, DAISY["age_months"]) and contains_months(answer, PEPPER["age_months"]),
                f"expected={DAISY['age_months']} and {PEPPER['age_months']} months, answer={answer!r}")
    judge.check("answer_has_both_fees", contains_money(answer, DAISY["fee"]) and contains_money(answer, PEPPER["fee"]),
                f"expected=${DAISY['fee']} and ${PEPPER['fee']}, answer={answer!r}")
    judge.check("answer_identifies_lower_fee_pet", identifies(answer, PEPPER["name"], [DAISY["name"]], LOWEST, HIGHEST),
                f"winner={PEPPER['name']!r}, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
