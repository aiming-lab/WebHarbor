#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--7.

Open About; report undergraduate and graduate enrollment and their difference.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, final_answer, load_run, parse_args, visited_path,
)

from answer_checks import bound_count, difference

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
        bound_count(answer, 46820, ("undergraduate", "undergraduates", "undergrads")),
        repr(answer),
    )
    judge.check(
        "graduate_bound",
        bound_count(answer, 14000, ("graduate", "graduates", "graduate students")),
        repr(answer),
    )
    judge.check("exact_difference", difference(answer, 32820), repr(answer))
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
