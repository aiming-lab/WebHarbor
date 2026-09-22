#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--2.

Open Athletics, then football and wrestling details; both list the same conference.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, clicked_details_from_listing, contains_all, final_answer, load_run, parse_args, visited_in_order,
)

TASK_ID = 'Ohio State University--2'

FOOTBALL = "/athletics/ohio-state-buckeyes-football"
WRESTLING = "/athletics/ohio-state-buckeyes-wrestling"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "athletics_then_both_details",
        visited_in_order(trajectory, [("/athletics", {}), (FOOTBALL, {})])
        and visited_in_order(trajectory, [("/athletics", {}), (WRESTLING, {})]),
        "listing precedes details",
    )
    judge.check(
        "clicked_both_teams",
        clicked_details_from_listing(trajectory, "/athletics", (FOOTBALL, WRESTLING)),
        "visible team links used",
    )
    judge.check(
        "answer_big_ten_both",
        contains_all(answer, ("Big Ten",)),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
