#!/usr/bin/env python3
"""Verify UC Berkeley--14: College of Engineering enrolment counts and dean.

The university-wide totals on the homepage/About page (31,800 / 12,000) are the
near-miss distractors: the card values are per-college.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_count,
    contains_person,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--14"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 14)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_visited_path(judge, trajectory, "visited_academics_page", "/academics")
    judge.check(
        "answer_has_undergrad_count",
        contains_count(answer, facts["undergrad_count"]),
        f"expected_undergrad_count={facts['undergrad_count']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_grad_count",
        contains_count(answer, facts["grad_count"]),
        f"expected_grad_count={facts['grad_count']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_dean",
        contains_person(answer, facts["dean"]),
        f"expected_dean={facts['dean']!r}, answer={answer!r}",
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
