#!/usr/bin/env python3
"""Verify Walmart Careers--8: Two Mississippi Auto Care Center Technician postings: store number with more open positions + that count (read-only).

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
    check_trajectory_identity,
    check_visited_job_detail,
    contains_positions_count,
    fail_closed,
    final_answer,
    load_run,
    mentions_store_number,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "Walmart Careers--8"
WINNER_ID = "CP-1230-11592"
LOSER_ID = "CP-954-10637"
WINNER_STORE = 1230
LOSER_STORE = 954
POSITIONS = 5


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_job_detail(judge, trajectory, WINNER_ID)
    check_visited_job_detail(judge, trajectory, LOSER_ID)
    judge.check(
        "answer_names_winning_store_number",
        mentions_store_number(answer, WINNER_STORE),
        f"expected_store={WINNER_STORE!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_positions_count",
        contains_positions_count(answer, POSITIONS),
        f"expected={POSITIONS!r}, answer={answer!r}",
    )
    judge.check(
        "answer_does_not_name_other_store_instead",
        not (mentions_store_number(answer, LOSER_STORE) and not mentions_store_number(answer, WINNER_STORE)),
        f"winner_store={WINNER_STORE!r}, loser_store={LOSER_STORE!r}, answer={answer!r}",
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
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
