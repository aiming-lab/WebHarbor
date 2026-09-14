#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--15.

From Athletics, open wrestling and fencing; compare national championship counts.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, affirmative_contains, check_common, check_read_only, clicked_transition,
    contains_any, final_answer, has_number, load_run, number_bound_in_comparison,
    parse_args, visited_in_order
)

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
        clicked_transition(trajectory, "/athletics", WRESTLING)
        and clicked_transition(trajectory, "/athletics", FENCING),
        "visible team links used",
    )
    judge.check(
        "wrestling_titles_bound",
        number_bound_in_comparison(answer, 8, ("wrestling",)),
        repr(answer),
    )
    judge.check(
        "fencing_titles_bound",
        number_bound_in_comparison(answer, 2, ("fencing",)),
        repr(answer),
    )
    judge.check(
        "winner_and_difference",
        affirmative_contains(answer, "wrestling")
        and contains_any(answer, ("more", "higher"))
        and has_number(answer, 6),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
