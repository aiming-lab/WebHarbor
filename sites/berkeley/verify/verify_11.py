#!/usr/bin/env python3
"""Verify UC Berkeley--11: the freshman deadline and the acceptance rate.

Both values are rendered from tracked source rather than the DB; the verifier
derives them from templates/admissions.html and fails closed if the labelled
literals move, and verify/tests asserts they are not DB-derived.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_month_day,
    contains_percent,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--11"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 11)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_visited_path(judge, trajectory, "visited_admissions_page", "/admissions")
    judge.check(
        "answer_has_freshman_deadline",
        contains_month_day(answer, facts["deadline"]),
        f"expected_deadline={facts['deadline']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_acceptance_rate",
        contains_percent(answer, facts["acceptance_rate"]),
        f"expected_acceptance_rate={facts['acceptance_rate']!r}, answer={answer!r}",
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
