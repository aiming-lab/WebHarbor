#!/usr/bin/env python3
"""Verify Amtrak--14: Compare ANA vs SBA station pages: which supports checked baggage (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    affirmative_clauses_mentioning,
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--14"
YES_STATION = ["SBA", "Santa Barbara"]
NO_STATION = ["ANA", "Anaheim"]


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_station_ANA", "/stations/ANA")
    check_visited_path(judge, trajectory, "visited_station_SBA", "/stations/SBA")
    yes_clauses = affirmative_clauses_mentioning(answer, YES_STATION)
    no_clauses = affirmative_clauses_mentioning(answer, NO_STATION)
    judge.check("answer_names_checked_baggage_station", bool(yes_clauses) and not no_clauses,
                f"expected_affirmed={YES_STATION!r}, expected_not_affirmed={NO_STATION!r}, affirmed_yes={yes_clauses!r}, affirmed_no={no_clauses!r}, answer={answer!r}")
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
