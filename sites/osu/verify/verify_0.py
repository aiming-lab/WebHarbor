#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--0.

Open Academics and report the Fisher College of Business dean.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, clicked_transition, contains_all,
    final_answer, load_run, parse_args, visited_path
)

TASK_ID = 'Ohio State University--0'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("opened_academics", visited_path(trajectory, "/academics"), "required=/academics")
    judge.check("used_academics_link", clicked_transition(trajectory, "/", "/academics"), "home to academics click")
    judge.check(
        "answer_fisher_dean",
        contains_all(answer, ("Fisher College of Business", "Anil Makhija")),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
