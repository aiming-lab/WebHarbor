#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--18.

Open Research then James Cancer Hospital; report director and all four focus areas.

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

TASK_ID = 'Ohio State University--18'

PATH = "/research/james-cancer-hospital-and-solove-research-institute"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_james_navigation",
        visited_in_order(trajectory, [("/research", {}), (PATH, {})])
        and clicked_transition(trajectory, "/research", PATH),
        "research to James",
    )
    judge.check(
        "answer_director_focus",
        contains_all(
            answer,
            ("William Farrar", "Cancer research", "Oncology", "Clinical trials", "Precision medicine"),
        ),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
