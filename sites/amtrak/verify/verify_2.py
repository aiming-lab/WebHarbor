#!/usr/bin/env python3
"""Verify Amtrak--2: Round trip WAS->PHL 04-20 / PHL->WAS 04-22, fastest legs, fare page: per-traveler Business fare (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_paths_in_order,
    check_read_only,
    check_trajectory_identity,
    contains_money,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--2"
BUSINESS_PER_TRAVELER = 124.83  # Acela Express 2152 (WAS->PHL) + Acela Express 2151 (PHL->WAS)


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_paths_in_order(
        judge, trajectory, "round_trip_workflow_in_order",
        [("/booking/results", {"trip_type": "round-trip", "origin": "WAS", "destination": "PHL",
                               "departure_date": "2026-04-20", "return_date": "2026-04-22"}),
         ("/booking/results", {"leg": "return"}),
         ("/booking/select-trip", {}),
         ("/booking/select-fare", {})],
    )
    judge.check("answer_has_business_fare", contains_money(answer, BUSINESS_PER_TRAVELER),
                f"expected={BUSINESS_PER_TRAVELER!r}, answer={answer!r}")
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
