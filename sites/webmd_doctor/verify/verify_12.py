#!/usr/bin/env python3
"""Verify WebMD Doctor--12: Specialty menu: Cardiovascular Disease > Pennsylvania > West Chester, 4+ stars; the only male: fellowship + year (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_paths_in_order,
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_institution,
    contains_year,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--12"
SLUG = "joseph-iyer-29b88273"
LANDING = "/providers/specialty/cardiovascular-disease"
STATE_PAGE = LANDING + "/pennsylvania"
CITY_PAGE = STATE_PAGE + "/west-chester"
FELLOWSHIP = "Allegheny Ridge Medical Center"
FELLOWSHIP_YEAR = 1987


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_specialty_landing_page", LANDING)
    check_visited_path(judge, trajectory, "visited_state_page", STATE_PAGE)
    check_visited_path(judge, trajectory, "visited_city_page", CITY_PAGE)
    check_results_visited(judge, trajectory, "visited_city_page_rated_4_up", {"minrating": "4"}, path=CITY_PAGE)
    check_visited_profile(judge, trajectory, SLUG)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [(LANDING, {}), (STATE_PAGE, {}), (CITY_PAGE, {}), (profile_path_pattern(SLUG), {})])
    judge.check("answer_has_fellowship", contains_institution(answer, FELLOWSHIP), f"expected={FELLOWSHIP!r}, answer={answer!r}")
    judge.check("answer_has_fellowship_year", contains_year(answer, FELLOWSHIP_YEAR), f"expected={FELLOWSHIP_YEAR!r}, answer={answer!r}")
    # The FILTERED city page (minrating=4) must precede the profile visit; the
    # task says the list "must then be filtered" before the profile is opened.
    check_paths_in_order(
        judge, trajectory, "filtered_city_precedes_profile",
        [(CITY_PAGE, {"minrating": "4"}), (profile_path_pattern(SLUG), {})],
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
