#!/usr/bin/env python3
"""Verify WebMD Doctor--10: Psychiatrists near Newark accepting Medicaid rated 4+; the virtual-visit one: wait time + residency (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    profile_path_pattern,
    check_visited_before,
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_profile,
    contains_institution,
    contains_minutes,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    NEWARK,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--10"
SLUG = "veronica-nwachukwu-71051d38"
WAIT_MINUTES = 25
RESIDENCY = "Rappahannock University Hospital"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(
        judge, trajectory, "visited_medicaid_rated_results",
        {"q": r"psychiatr", "medicaid": True, "minrating": "4", "loc": NEWARK},
        {"sids": "7", "medicaid": True, "minrating": "4", "loc": NEWARK},
    )
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_wait_minutes", contains_minutes(answer, WAIT_MINUTES), f"expected={WAIT_MINUTES!r} minutes, answer={answer!r}")
    judge.check("answer_has_residency", contains_institution(answer, RESIDENCY), f"expected={RESIDENCY!r}, answer={answer!r}")
    check_visited_before(
        judge, trajectory, "filtered_results_precede_profile", "/results", profile_path_pattern(SLUG),
        before_params=[
            {"q": r"psychiatr", "medicaid": True, "minrating": "4", "loc": NEWARK},
            {"sids": "7", "medicaid": True, "minrating": "4", "loc": NEWARK},
        ],
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
