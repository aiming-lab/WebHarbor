#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--1.

Open About and report the Varsity Sports figure shown on that page.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, final_answer, load_run, parse_args, visited_path,
)

from answer_checks import varsity_count

TASK_ID = 'Ohio State University--1'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("opened_about", visited_path(trajectory, "/about"), "required=/about")
    judge.check(
        "answer_varsity_sports",
        varsity_count(answer),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
