#!/usr/bin/env python3
"""Verify UC Berkeley--25: the Spring Career Fair plus two other Career events.

The anchor event is derived by name (it survives the frozen clock), its detail
page is gated, and the other two events must bind title + date + location to
distinct rows of the Career listing.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    affirmative_near,
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
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


TASK_ID = "UC Berkeley--25"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 25)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    anchor = facts["anchor"]

    check_params_visited(judge, trajectory, "visited_career_events_listing", "/events", {"category": "Career"})
    check_visited_detail(judge, trajectory, "event", anchor["id"])
    judge.check(
        "answer_has_anchor_date",
        contains_date(answer, str(anchor["start_datetime"])[:10]),
        f"expected_date={str(anchor['start_datetime'])[:10]!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_anchor_location",
        contains_location(answer, anchor["location"]),
        f"expected_location={anchor['location']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_registration_required",
        affirmative_near(answer, "career fair", "required", 200)
        or affirmative_near(answer, anchor["title"], "required", 200),
        f"answer={answer!r}",
    )
    matched = [
        row for row in facts["others"]
        if title_tokens_matched(answer, row["title"]) >= 3
        and contains_date(answer, str(row["start_datetime"])[:10])
        and contains_location(answer, row["location"])
    ]
    judge.check(
        "answer_lists_two_other_career_events",
        len(matched) >= 2,
        f"matched_events={[row['id'] for row in matched]!r} of {len(facts['others'])} other Career events; "
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
