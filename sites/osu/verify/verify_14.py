#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--14.

From Athletics, open football and men's basketball; report each home venue.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, clicked_transition, final_answer,
    load_run, parse_args, text_bound_in_comparison, visited_in_order
)

TASK_ID = 'Ohio State University--14'

FOOTBALL = "/athletics/ohio-state-buckeyes-football"
BASKETBALL = "/athletics/ohio-state-buckeyes-mens-basketball"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "athletics_then_both_details",
        visited_in_order(trajectory, [("/athletics", {}), (FOOTBALL, {})])
        and visited_in_order(trajectory, [("/athletics", {}), (BASKETBALL, {})]),
        "listing before details",
    )
    judge.check(
        "clicked_both_teams",
        clicked_transition(trajectory, "/athletics", FOOTBALL)
        and clicked_transition(trajectory, "/athletics", BASKETBALL),
        "visible team links used",
    )
    judge.check(
        "football_venue_bound",
        text_bound_in_comparison(answer, "Ohio Stadium", ("football",)),
        repr(answer),
    )
    judge.check(
        "basketball_venue_bound",
        text_bound_in_comparison(answer, "Value City Arena", ("basketball",)),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
