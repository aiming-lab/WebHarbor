#!/usr/bin/env python3
"""Verify UC Berkeley--19: an Athletics championship article, summarised.

Set-valued: the accepted championship set is derived from the Athletics rows
(titles carrying "championship"); the summary must bind to one of them — a
medals/football/academic-rating article fails.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    contains_phrase,
    detail_visited,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
    title_tokens_matched,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--19"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 19)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_params_visited(judge, trajectory, "visited_athletics_listing", "/news", {"category": "Athletics"})
    visited = [row for row in facts["championships"] if detail_visited(trajectory, "news", row["slug"])]
    judge.check(
        "visited_championship_article",
        bool(visited),
        f"championships={[row['slug'] for row in facts['championships']]!r}",
    )
    bound = [
        row for row in visited
        if title_tokens_matched(answer, row["title"]) >= 3 and contains_phrase(answer, "championship")
    ]
    judge.check(
        "answer_binds_to_championship_article",
        bool(bound),
        f"visited={[row['title'] for row in visited]!r}, "
        f"title_token_hits={[title_tokens_matched(answer, row['title']) for row in visited]!r}; "
        f"answer={answer!r}",
    )
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
