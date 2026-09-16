#!/usr/bin/env python3
"""Verify UC Berkeley--10: BAIR's director and founding year.

The seed diverges from the real-world founding year (2017), so a remembered
value fails; both facts are read off the centre page.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
    contains_person,
    contains_year,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--10"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 10)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_visited_detail(judge, trajectory, "research", facts["centre"]["slug"])
    judge.check(
        "answer_has_director",
        contains_person(answer, facts["director"]),
        f"expected_director={facts['director']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_founded_year",
        contains_year(answer, facts["founded_year"]),
        f"expected_founded_year={facts['founded_year']!r}, answer={answer!r}",
    )
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
