#!/usr/bin/env python3
"""Verify WebMD Doctor--7: Dr. Lillian Acosta (OBGYN, Salem): criterion with most needs-improvement votes + average wait (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_profile,
    contains_any,
    contains_minutes,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--7"
SLUG = "lillian-acosta-4a89e15e"
CRITERION = ("Staff was courteous", "Staff courteous")
WAIT_MINUTES = 15


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_worst_criterion", contains_any(answer, CRITERION), f"expected={CRITERION[0]!r}, answer={answer!r}")
    judge.check("answer_has_wait_minutes", contains_minutes(answer, WAIT_MINUTES), f"expected={WAIT_MINUTES!r} minutes, answer={answer!r}")
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
