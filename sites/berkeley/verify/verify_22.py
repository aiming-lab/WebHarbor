#!/usr/bin/env python3
"""Verify UC Berkeley--22: how many departments the College of Letters and Science lists.

The /departments page carries no per-college total (and the stale
``colleges.dept_count`` column is never rendered), so the count is enumeration
work: the answer must carry it and name several of the listed departments.
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
    contains_department,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--22"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 22)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    count = len(facts["departments"])

    check_visited_path(judge, trajectory, "visited_departments_page", "/departments")
    judge.check(
        "answer_has_department_count",
        contains_count(answer, count),
        f"expected_count={count!r}, answer={answer!r}",
    )
    named = [row["name"] for row in facts["departments"] if contains_department(answer, row["name"])]
    judge.check(
        "answer_names_ls_departments",
        len(named) >= 4,
        f"named={named!r} of {[row['name'] for row in facts['departments']]!r}; answer={answer!r}",
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
