#!/usr/bin/env python3
"""Verify Amtrak--12: CHI->DEN 2026-04-20: route name and Flexible price (read-only).

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
    contains_money,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
    resolve_snapshots,
    results_visited,
)


TASK_ID = "Amtrak--12"
ROUTE = "California Zephyr"
FLEXIBLE_PRICE = 96.56


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_results_visited(judge, trajectory, "visited_results_chi_den_0420",
                          {"origin": "CHI", "destination": "DEN", "departure_date": "2026-04-20"})
    judge.check("flexible_price_page_opened",
                results_visited(trajectory, origin="CHI", destination="DEN", departure_date="2026-04-20", fare_class="flexible")
                or navigated_to_path(trajectory, "/booking/select-fare"),
                "required=/booking/results?...&fare_class=flexible OR /booking/select-fare")
    judge.check("answer_names_route", contains_all(answer, [ROUTE]), f"expected={ROUTE!r}, answer={answer!r}")
    judge.check("answer_has_flexible_price", contains_money(answer, FLEXIBLE_PRICE), f"expected={FLEXIBLE_PRICE!r}, answer={answer!r}")
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
