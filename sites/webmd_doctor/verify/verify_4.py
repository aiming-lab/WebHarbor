#!/usr/bin/env python3
"""Verify WebMD Doctor--4: Dr. Charles Villanueva (Orthopedic Surgery, Elkton): board + certification year + residency (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_profile,
    contains_any,
    contains_institution,
    contains_year,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--4"
SLUG = "charles-villanueva-13e969b2"
BOARDS = ("American Board of Orthopaedic Surgery", "American Board of Orthopedic Surgery")
CERT_YEAR = 2014
RESIDENCY = "Blue Ridge Regional Medical Center"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_certifying_board", contains_any(answer, BOARDS), f"expected={BOARDS[0]!r}, answer={answer!r}")
    judge.check("answer_has_certification_year", contains_year(answer, CERT_YEAR), f"expected={CERT_YEAR!r}, answer={answer!r}")
    judge.check("answer_has_residency", contains_institution(answer, RESIDENCY), f"expected={RESIDENCY!r}, answer={answer!r}")
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
