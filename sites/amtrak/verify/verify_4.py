#!/usr/bin/env python3
"""Verify Amtrak--4: SEA->LAX 2026-04-22 for 2, sleeper-room selection: cheapest room type + extra cost (read-only).

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
    check_results_visited,
    check_trajectory_identity,
    contains_money,
    contains_word,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--4"
ROOM_TYPE = "Roomette"
EXTRA_COST = 316.00


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_sea_lax_0422_two_passengers",
                          {"origin": "SEA", "destination": "LAX", "departure_date": "2026-04-22", "passengers": "2"})
    check_paths_in_order(
        judge, trajectory, "sleeper_workflow_in_order",
        [("/booking/results", {"origin": "SEA", "destination": "LAX"}), ("/booking/select-trip", {}),
         ("/booking/select-fare", {}), ("/booking/rooms", {})],
    )
    judge.check("answer_names_room_type", contains_word(answer, ROOM_TYPE), f"expected={ROOM_TYPE!r}, answer={answer!r}")
    judge.check("answer_has_extra_cost", contains_money(answer, EXTRA_COST), f"expected={EXTRA_COST!r}, answer={answer!r}")
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
