#!/usr/bin/env python3
"""Verify Walmart Careers--6: Cleveland, OH location; Online Order Filling Team Supervisor: street + open positions (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_job_detail,
    contains_positions_count,
    contains_street,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Walmart Careers--6"
JOB_ID = "CP-2073-11104"
STREET = "10000 Brookpark Rd"
POSITIONS = 2


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(
        judge,
        trajectory,
        "visited_results_required_filters",
        {"loc": "cleveland", "radius": "25", "type": "Full time", "shift": "Weekday Day"},
    )
    check_visited_job_detail(judge, trajectory, JOB_ID)
    judge.check(
        "answer_has_street_address",
        contains_street(answer, STREET),
        f"expected={STREET!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_positions_count",
        contains_positions_count(answer, POSITIONS),
        f"expected={POSITIONS!r}, answer={answer!r}",
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
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
