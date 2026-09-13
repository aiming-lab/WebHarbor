#!/usr/bin/env python3
"""Verify Amtrak--0: NYP->WAS 2026-04-20 sorted by duration; fastest direct service: route, train number, travel time (read-only).

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
    contains_duration,
    contains_word,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--0"
ROUTE = "Acela Express"
TRAIN_NUMBER = "2151"
# The option summary prints 2h 50m (departure to arrival, incl. the PHL dwell); the
# segment tag on the same card prints 2h 46m (pure running time). Both are on the page.
DURATIONS = [(2, 50), (2, 46)]


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_nyp_was_0420_sorted_by_duration",
                          {"origin": "NYP", "destination": "WAS", "departure_date": "2026-04-20", "sort": "duration"})
    judge.check("answer_names_route", contains_all(answer, [ROUTE]), f"expected={ROUTE!r}, answer={answer!r}")
    judge.check("answer_has_train_number", contains_word(answer, TRAIN_NUMBER), f"expected={TRAIN_NUMBER!r}, answer={answer!r}")
    judge.check("answer_has_travel_time", any(contains_duration(answer, h, m) for h, m in DURATIONS),
                f"expected_any={[f'{h}h {m}m' for h, m in DURATIONS]!r}, answer={answer!r}")
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
