#!/usr/bin/env python3
"""Deterministic verifier for Ohio State University--17.

Search cancer research, open the immunotherapy article; report exact title and author.

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

TASK_ID = 'Ohio State University--17'

PATH = "/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy"
TITLE = "Ohio State Researchers Develop Breakthrough Cancer Immunotherapy"


def main() -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    judge.check(
        "ordered_cancer_search",
        visited_in_order(trajectory, [("/search", {"q": "cancer research"}), (PATH, {})])
        and clicked_transition(trajectory, "/search", PATH),
        "search to exact article",
    )
    judge.check("answer_title_author", contains_all(answer, (TITLE, "Jody Sheridan")), repr(answer))
    check_read_only(judge, args)
    judge.emit()

if __name__ == "__main__":
    main()
