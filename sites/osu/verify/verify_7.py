#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--7.

Open About; report undergraduate and graduate enrollment and their difference.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, final_answer, has_number, load_run,
    number_bound_in_comparison, parse_args, visited_path
)

TASK_ID = 'Ohio State University--7'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("opened_about", visited_path(trajectory, "/about"), "required=/about")
    judge.check(
        "undergraduate_bound",
        number_bound_in_comparison(answer, 46820, ("undergraduate", "undergrads")),
        repr(answer),
    )
    judge.check(
        "graduate_bound",
        number_bound_in_comparison(answer, 14000, ("graduate", "graduate students")),
        repr(answer),
    )
    judge.check("exact_difference", has_number(answer, 32820), repr(answer))
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
