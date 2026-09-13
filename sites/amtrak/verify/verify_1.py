#!/usr/bin/env python3
"""Verify Amtrak--1: NYP->WAS 2026-04-20 with transfers, sorted by price; cheapest itinerary: route + starting fare (read-only).

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
    contains_all,
    contains_money,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--1"
ROUTE = "Northeast Regional"
STARTING_FARE = 26.88


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_nyp_was_0420_price_with_transfers",
                          {"origin": "NYP", "destination": "WAS", "departure_date": "2026-04-20",
                           "sort": ("price", None), "direct_only": (None, "0", "false", "off")})
    judge.check("answer_names_route", contains_all(answer, [ROUTE]), f"expected={ROUTE!r}, answer={answer!r}")
    judge.check("answer_has_starting_fare", contains_money(answer, STARTING_FARE), f"expected={STARTING_FARE!r}, answer={answer!r}")
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
