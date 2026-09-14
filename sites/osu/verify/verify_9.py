#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--9.

Use Programs college=engineering; report distinct degree types and how many.

Ground truth is hardcoded here, never in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge, check_common, check_read_only, contains_word, final_answer,
    has_number, load_run, parse_args, visited_query
)

TASK_ID = 'Ohio State University--9'


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "engineering_filter",
        visited_query(trajectory, "/programs", {"college": "engineering"}),
        "college=engineering",
    )
    judge.check(
        "answer_all_types",
        all(contains_word(answer, value) for value in ("BS", "MS", "PhD")) and has_number(answer, 3),
        repr(answer),
    )
    judge.check(
        "no_extra_degree_types",
        not any(
            contains_word(answer, value)
            for value in ("BA", "MA", "MBA", "JD", "MD", "MPH", "PharmD", "DVM", "OD")
        ),
        repr(answer),
    )
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
