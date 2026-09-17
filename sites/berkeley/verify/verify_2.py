#!/usr/bin/env python3
"""Verify UC Berkeley--2: the Computer Science BS requirements block.

Three same-name programmes (BS/MS/PhD) make the detail slug the discriminator;
the sibling requirement items are derived from the snapshot and must not appear.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    mentions,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--2"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 2)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_params_visited(
        judge, trajectory, "visited_program_search", "/programs",
        {"q": "computer science"}, {"degree": "BS"},
    )
    check_visited_detail(judge, trajectory, "program", facts["program"]["slug"])
    matched = mentions(answer, facts["items"])
    judge.check(
        "answer_requirements_match_bs",
        len(matched) >= 4,
        f"matched_items={sorted(matched)!r} of {facts['items']!r}; answer={answer!r}",
    )
    foreign = mentions(answer, facts["foreign_items"])
    judge.check(
        "answer_no_sibling_requirements",
        not foreign,
        f"foreign_items_matched={sorted(foreign)!r}; answer={answer!r}",
    )
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
