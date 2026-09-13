#!/usr/bin/env python3
"""Verify Amtrak--3: Multi-city SEA->PDX 04-18, PDX->SAC 04-20, SAC->LAX 04-22, cheapest legs, fare page: per-traveler Value fare (read-only).

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


TASK_ID = "Amtrak--3"
VALUE_PER_TRAVELER = 169.65  # Amtrak Cascades 506 + Coast Starlight 14 + Coast Starlight 14


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_paths_in_order(
        judge, trajectory, "multi_city_workflow_in_order",
        [("/booking/multi-city", {}), ("/booking/select-trip", {}), ("/booking/select-fare", {})],
    )
    judge.check("answer_has_value_fare", contains_money(answer, VALUE_PER_TRAVELER),
                f"expected={VALUE_PER_TRAVELER!r}, answer={answer!r}")
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
