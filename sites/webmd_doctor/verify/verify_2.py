#!/usr/bin/env python3
"""Verify WebMD Doctor--2: Family Medicine search near Newark; Dr. Ruth Thackeray: primary office phone + Saturday hours (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    profile_path_pattern,
    contains_saturday_hours,
    check_visited_before,
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_profile,
    contains_hours_window,
    contains_phone,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    NEWARK,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--2"
SLUG = "ruth-thackeray-45234b97"
PHONE = "(302) 555-1542"
SAT_OPEN = "8:00 am"
SAT_CLOSE = "1:00 pm"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_family_medicine_search", {"q": r"family", "loc": NEWARK}, {"sids": "3", "loc": NEWARK})
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_primary_office_phone", contains_phone(answer, PHONE), f"expected={PHONE!r}, answer={answer!r}")
    judge.check("answer_has_saturday_hours", contains_hours_window(answer, SAT_OPEN, SAT_CLOSE), f"expected={SAT_OPEN!r}-{SAT_CLOSE!r}, answer={answer!r}")
    judge.check(
        "answer_has_saturday_hours_context",
        contains_saturday_hours(answer, SAT_OPEN, SAT_CLOSE),
        f"both endpoints must sit in one Saturday clause in order; answer={answer!r}",
    )
    check_visited_before(
        judge, trajectory, "results_precede_profile", "/results", profile_path_pattern(SLUG),
        before_params=[{"q": r"family", "loc": NEWARK}, {"sids": "3", "loc": NEWARK}],
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
