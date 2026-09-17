#!/usr/bin/env python3
"""Verify UC Berkeley--6: at least three Lecture events with dates and locations.

Set-valued: the accepted set is every seeded Lecture event (the ``date=all``
rendering); each reported event must bind title + date + location to one row.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    contains_date,
    contains_location,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
    title_tokens_matched,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--6"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 6)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_params_visited(judge, trajectory, "visited_lecture_listing", "/events", {"category": "Lecture"})
    matched = [
        row for row in facts["events"]
        if title_tokens_matched(answer, row["title"]) >= 3
        and contains_date(answer, str(row["start_datetime"])[:10])
        and contains_location(answer, row["location"])
    ]
    judge.check(
        "answer_lists_three_lecture_events",
        len(matched) >= 3,
        f"matched_events={[row['id'] for row in matched]!r} of {len(facts['events'])} Lecture events; "
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
