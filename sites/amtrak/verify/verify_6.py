#!/usr/bin/env python3
"""Verify Amtrak--6: Public trip lookup ALGX87 with Alice's email: route name + departure date (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_all,
    contains_date,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--6"
BOOKING_CODE = "ALGX87"
ROUTE = "Acela Express"
DEPARTURE = date(2026, 4, 20)


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_trip_lookup", "/trip-lookup")
    check_visited_path(judge, trajectory, "visited_trip_detail", f"/trip/{BOOKING_CODE}")
    judge.check("answer_names_route", contains_all(answer, [ROUTE]), f"expected={ROUTE!r}, answer={answer!r}")
    judge.check("answer_has_departure_date", contains_date(answer, DEPARTURE), f"expected={DEPARTURE.isoformat()!r}, answer={answer!r}")
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
