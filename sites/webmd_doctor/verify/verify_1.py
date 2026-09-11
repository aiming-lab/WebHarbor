#!/usr/bin/env python3
"""Verify WebMD Doctor--1: Dr. Julian Zamora (Cardiovascular Disease, Wilmington): NPI + languages (read-only).

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
    contains_all,
    contains_npi,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--1"
SLUG = "julian-zamora-d412b77d"
NPI = "1438496704"
LANGUAGES = ("English", "Tagalog", "Portuguese")


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_npi", contains_npi(answer, NPI), f"expected={NPI!r}, answer={answer!r}")
    judge.check("answer_lists_languages", contains_all(answer, LANGUAGES), f"expected={LANGUAGES!r}, answer={answer!r}")
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
