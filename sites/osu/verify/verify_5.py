#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--5.

Open About; report founding year and original institution name.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, contains_all, final_answer,
    has_number, load_run, parse_args, visited_path
)

TASK_ID = 'Ohio State University--5'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("opened_about", visited_path(trajectory, "/about"), "required=/about")
    judge.check(
        "answer_founding",
        has_number(answer, 1870) and contains_all(answer, ("Ohio Agricultural and Mechanical College",)),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
