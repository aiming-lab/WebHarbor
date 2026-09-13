#!/usr/bin/env python3
"""Verify Amtrak--15: Help center: checked-baggage cutoff and which departures it applies to (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_any,
    fail_closed,
    final_answer,
    load_run,
    normalize_text,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Amtrak--15"
CUTOFF_PATTERN = r"(?<![\d])45\s*(?:-\s*)?(?:min|mins|minute|minutes)\b"
DEPARTURE_KIND = ["long-distance", "long distance"]


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_checked_baggage_timing_article", "/help/checked-baggage-timing")
    judge.check("answer_has_cutoff_minutes", bool(re.search(CUTOFF_PATTERN, normalize_text(answer))), f"expected=45 minutes, answer={answer!r}")
    judge.check("answer_names_departure_kind", contains_any(answer, DEPARTURE_KIND), f"expected_any={DEPARTURE_KIND!r}, answer={answer!r}")
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
