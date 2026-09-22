#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--4.

Search for research expenditures, open the record article, report amount and date.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (
    Judge, check_common, check_read_only, clicked_transition, final_answer, load_run, parse_args, visited_in_order,
)

from answer_checks import date_matches, money

TASK_ID = 'Ohio State University--4'

PATH = "/news/ohio-state-sets-record-for-research-expenditures-at-13-billion"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_news_search",
        visited_in_order(trajectory, [("/search", {"q": "research expenditures"}), (PATH, {})])
        and clicked_transition(trajectory, "/search", PATH),
        "search to exact article",
    )
    judge.check(
        "answer_amount_date",
        money(answer, 1_300_000_000) and date_matches(answer, 9, 23, 2024),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
