#!/usr/bin/env python3
"""Verify Amtrak--5: Alice signs in, My Trips: booking code / origin / departure date of the upcoming Denver trip (read-only).

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
    check_signed_in_as,
    check_trajectory_identity,
    check_visited_any_path,
    contains_code,
    contains_date,
    contains_word,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--5"
EMAIL = "alice.j@test.com"
BOOKING_CODE = "ALJDAM"
ORIGIN = "CHI"
DEPARTURE = date(2026, 4, 20)


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_visited_any_path(judge, trajectory, "visited_trips_list_or_trip_page", ["/account/trips", f"/trip/{BOOKING_CODE}"])
    judge.check("answer_has_booking_code", contains_code(answer, BOOKING_CODE), f"expected={BOOKING_CODE!r}, answer={answer!r}")
    judge.check("answer_has_origin_code", contains_word(answer, ORIGIN), f"expected={ORIGIN!r}, answer={answer!r}")
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
