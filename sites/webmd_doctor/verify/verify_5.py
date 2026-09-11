#!/usr/bin/env python3
"""Verify WebMD Doctor--5: Gastroenterologist search near Newark; Dr. Caroline Danforth: the More-Than-Most condition + first Top-20 entry (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_profile,
    contains_condition,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    NEWARK,
    parse_args,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--5"
SLUG = "caroline-danforth-7093653d"
MORE_THAN_MOST = "Acid Reflux (GERD)"
FIRST_TOP20 = "Anemia"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_gastroenterologist_search", {"q": r"gastroenterolog", "loc": NEWARK}, {"sids": "6", "loc": NEWARK})
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("answer_has_more_than_most_condition", contains_condition(answer, MORE_THAN_MOST), f"expected={MORE_THAN_MOST!r}, answer={answer!r}")
    judge.check("answer_has_first_top20_condition", contains_condition(answer, FIRST_TOP20), f"expected={FIRST_TOP20!r}, answer={answer!r}")
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
