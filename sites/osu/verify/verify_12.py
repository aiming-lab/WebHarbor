#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--12.

Search Programs for Juris Doctor, open JD detail; report type, credits, duration.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, clicked_transition, contains_all,
    contains_word, final_answer, has_number, load_run, parse_args, visited_in_order
)

TASK_ID = 'Ohio State University--12'

PATH = "/programs/juris-doctor-jd"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_jd_search",
        visited_in_order(trajectory, [("/programs", {"q": "Juris Doctor"}), (PATH, {})])
        and clicked_transition(trajectory, "/programs", PATH),
        "program search to JD",
    )
    judge.check(
        "answer_jd_details",
        contains_word(answer, "JD")
        and has_number(answer, 90)
        and has_number(answer, 3)
        and contains_all(answer, ("credits", "years")),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
