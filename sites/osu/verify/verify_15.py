#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--15.

From Athletics, open wrestling and fencing; compare national championship counts.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, clicked_details_from_listing, final_answer, load_run, parse_args, visited_in_order,
)

from answer_checks import bound_count, difference, winner

TASK_ID = 'Ohio State University--15'

WRESTLING = "/athletics/ohio-state-buckeyes-wrestling"
FENCING = "/athletics/ohio-state-buckeyes-fencing"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "athletics_then_both_details",
        visited_in_order(trajectory, [("/athletics", {}), (WRESTLING, {})])
        and visited_in_order(trajectory, [("/athletics", {}), (FENCING, {})]),
        "listing before details",
    )
    judge.check(
        "clicked_both_teams",
        clicked_details_from_listing(trajectory, "/athletics", (WRESTLING, FENCING)),
        "visible team links used",
    )
    judge.check(
        "wrestling_titles_bound",
        bound_count(answer, 8, ("wrestling",)),
        repr(answer),
    )
    judge.check(
        "fencing_titles_bound",
        bound_count(answer, 2, ("fencing",)),
        repr(answer),
    )
    judge.check(
        "winner_and_difference",
        difference(answer, 6) and winner(answer, ("wrestling",), ("fencing",)),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
