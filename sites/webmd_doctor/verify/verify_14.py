#!/usr/bin/env python3
"""Verify WebMD Doctor--14: Christina Creek Medical Center (Hospitals > Delaware): its two Psychiatrists, more recent board certification (read-only, both profiles).

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
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_doctor_name,
    contains_year,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--14"
HOSPITALS_STATE_PATH = "/hospitals/delaware"
HOSPITAL_PATH = "/hospital/christina-creek-medical-center"
WINNER_SLUG = "arjun-bouchard-f3c85053"
WINNER_FIRST, WINNER_LAST = "Arjun", "Bouchard"
CERT_YEAR = 2004
OTHER_SLUG = "colin-ellery-640b0a4a"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_delaware_hospitals_page", HOSPITALS_STATE_PATH)
    check_visited_path(judge, trajectory, "visited_hospital_page", HOSPITAL_PATH)
    check_visited_profile(judge, trajectory, WINNER_SLUG)
    check_visited_profile(judge, trajectory, OTHER_SLUG)
    for label, slug in (("winner", WINNER_SLUG), ("other", OTHER_SLUG)):
        check_paths_in_order(judge, trajectory, f"{label}_workflow_in_order", [(HOSPITALS_STATE_PATH, {}), (HOSPITAL_PATH, {}), (profile_path_pattern(slug), {})])
    judge.check("answer_names_more_recent_certification", contains_doctor_name(answer, WINNER_FIRST, WINNER_LAST), f"expected={WINNER_FIRST + ' ' + WINNER_LAST!r}, answer={answer!r}")
    judge.check("answer_has_certification_year", contains_year(answer, CERT_YEAR), f"expected={CERT_YEAR!r}, answer={answer!r}")
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
