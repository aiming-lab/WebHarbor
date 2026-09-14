#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--8.

Open Academics; compare Engineering vs Fisher undergraduate counts.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, affirmative_contains, check_common, check_read_only, contains_any,
    final_answer, has_number, load_run, number_bound_in_comparison, parse_args,
    visited_path
)

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
        number_bound_in_comparison(answer, 8000, ("Engineering",)),
        repr(answer),
    )
    judge.check(
        "fisher_count_bound",
        number_bound_in_comparison(answer, 4500, ("Fisher",)),
        repr(answer),
    )
    judge.check(
        "difference_and_winner",
        has_number(answer, 3500)
        and affirmative_contains(answer, "Engineering")
        and contains_any(answer, ("more", "higher")),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
