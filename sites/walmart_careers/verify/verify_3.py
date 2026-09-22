#!/usr/bin/env python3
"""Verify Walmart Careers--3: Healthcare area -> Pharmacy Services -> Bentonville Pharmacy Technician: hashtag + open positions (read-only).

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
    check_visited_path,
    contains_positions_count,
    contains_hashtag,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Walmart Careers--3"
JOB_ID = "CP-5260-11531"
AREA_PATH = "/careers-areas/healthcare"
HASHTAG = "#pharmacytechjobs"
POSITIONS = 2


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_healthcare_area_page", AREA_PATH)
    check_results_visited(
        judge,
        trajectory,
        "visited_healthcare_results",
        {"category": "pharmacy-services"},
        {"area": "healthcare"},
    )
    check_visited_job_detail(judge, trajectory, JOB_ID)
    from verify_lib import check_paths_in_order
    check_paths_in_order(
        judge, trajectory, "workflow_in_order",
        [(AREA_PATH, {}), ("/results", {"area": "healthcare"}), (f"/jobs/{JOB_ID}", {})],
    )
    judge.check(
        "answer_has_hashtag",
        contains_hashtag(answer, HASHTAG),
        f"expected={HASHTAG!r}, answer={answer!r}",
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
