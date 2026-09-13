#!/usr/bin/env python3
"""Verify WebMD Doctor--3: Dr. Mateo Alvarado (Neurology, West Chester): the non-primary office name + street (read-only).

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
    contains_institution,
    contains_street,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--3"
SLUG = "mateo-alvarado-f727bd61"
OFFICE_NAME = "Providence Road Medical Group - Professional Plaza"
STREET = "3543 Baltimore Pike"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_other_office_name", contains_institution(answer, OFFICE_NAME), f"expected={OFFICE_NAME!r}, answer={answer!r}")
    judge.check("answer_has_other_office_street", contains_street(answer, STREET), f"expected={STREET!r}, answer={answer!r}")
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
