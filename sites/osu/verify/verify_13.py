#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--13.

Open Departments then Mathematics; report chair and location.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, clicked_transition, contains_all,
    final_answer, load_run, parse_args, visited_in_order
)

TASK_ID = 'Ohio State University--13'

PATH = "/departments/department-of-mathematics"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_math_navigation",
        visited_in_order(trajectory, [("/departments", {}), (PATH, {})])
        and clicked_transition(trajectory, "/departments", PATH),
        "departments to Mathematics",
    )
    judge.check(
        "answer_chair_and_location",
        contains_all(answer, ("James Cogdell", "100 Mathematics Building")),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
