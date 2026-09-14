#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--16.

Use Programs degree=MBA, open MBA detail; report deadline, credits, GRE.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, affirmative_contains, check_common, check_read_only, clicked_transition,
    contains_all, contains_word, final_answer, load_run, parse_args,
    visited_in_order, visited_query
)

TASK_ID = 'Ohio State University--16'

PATH = "/programs/master-of-business-administration-mba"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check("mba_filter", visited_query(trajectory, "/programs", {"degree": "MBA"}), "degree=MBA")
    judge.check(
        "ordered_mba_navigation",
        visited_in_order(trajectory, [("/programs", {"degree": "MBA"}), (PATH, {})])
        and clicked_transition(trajectory, "/programs", PATH),
        "filtered programs to MBA",
    )
    judge.check(
        "answer_mba_details",
        contains_all(answer, ("April 1", "credits"))
        and contains_word(answer, "60")
        and contains_word(answer, "GRE")
        and affirmative_contains(answer, "not required"),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
