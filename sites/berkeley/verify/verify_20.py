#!/usr/bin/env python3
"""Verify UC Berkeley--20: the JD programme's duration, deadline and school.

The Optometry MD shares the February 1 deadline and the MBA shares the
"professional degree" register; only the JD row has all three values.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
    contains_duration_years,
    contains_month_day,
    contains_phrase,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--20"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 20)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_params_visited(
        judge, trajectory, "visited_program_search", "/programs",
        {"degree": "JD"}, {"q": "juris"},
    )
    check_visited_detail(judge, trajectory, "program", facts["program"]["slug"])
    judge.check(
        "answer_has_duration",
        contains_duration_years(answer, facts["duration_years"]),
        f"expected_duration_years={facts['duration_years']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_deadline",
        contains_month_day(answer, facts["deadline"]),
        f"expected_deadline={facts['deadline']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_school",
        contains_phrase(answer, facts["college"]),
        f"expected_school={facts['college']!r}, answer={answer!r}",
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
