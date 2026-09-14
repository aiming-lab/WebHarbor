#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--3.

From Athletics, open football detail; report head coach and recent record.

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

TASK_ID = 'Ohio State University--3'

PATH = "/athletics/ohio-state-buckeyes-football"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_football_navigation",
        visited_in_order(trajectory, [("/athletics", {}), (PATH, {})])
        and clicked_transition(trajectory, "/athletics", PATH),
        "athletics listing to football",
    )
    judge.check("answer_coach_and_record", contains_all(answer, ("Ryan Day", "11-2")), repr(answer))
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
