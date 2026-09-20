#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--8.

Open Academics; compare Engineering vs Fisher undergraduate counts.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, final_answer, load_run, parse_args, visited_path,
)

from answer_checks import bound_count, difference, winner

TASK_ID = 'Ohio State University--8'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("opened_academics", visited_path(trajectory, "/academics"), "required=/academics")
    judge.check(
        "engineering_count_bound",
        bound_count(answer, 8000, ("Engineering",)),
        repr(answer),
    )
    judge.check(
        "fisher_count_bound",
        bound_count(answer, 4500, ("Fisher",)),
        repr(answer),
    )
    judge.check(
        "difference_and_winner",
        difference(answer, 3500) and winner(answer, ("Engineering",), ("Fisher",)),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
