#!/usr/bin/env python3
"""Verify Walmart Careers--9: Two Marcy, NY Freight Handler postings: the earlier shift start, its requisition ID + window (read-only).

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
    check_trajectory_identity,
    check_visited_job_detail,
    contains_req_id,
    contains_shift_window,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Walmart Careers--9"
JOB_ID = "CP-6038-10642"
LOSER_ID = "CP-9046-10913"
SHIFT_START = "3:00pm"
SHIFT_END = "7:30pm"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_job_detail(judge, trajectory, JOB_ID)
    check_visited_job_detail(judge, trajectory, LOSER_ID)
    judge.check(
        "answer_has_requisition_id",
        contains_req_id(answer, JOB_ID),
        f"expected={JOB_ID!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_shift_window",
        contains_shift_window(answer, SHIFT_START, SHIFT_END),
        f"expected={SHIFT_START!r}-{SHIFT_END!r}, answer={answer!r}",
    )
    judge.check(
        "answer_does_not_report_other_posting_instead",
        not (contains_req_id(answer, LOSER_ID) and not contains_req_id(answer, JOB_ID)),
        f"winner={JOB_ID!r}, loser={LOSER_ID!r}, answer={answer!r}",
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
