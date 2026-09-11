#!/usr/bin/env python3
"""Verify WebMD Doctor--16: Bob signs in, Pediatrician search near Newark, saves Dr. Anita Castellano, confirms in Saved Providers (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_exact_delta,
    check_paths_in_order,
    check_results_visited,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_any,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    NEWARK,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    saved_delta,
)


TASK_ID = "WebMD Doctor--16"
SLUG = "anita-castellano-14da1f29"
DOCTOR_ID = 163
EMAIL = "bob.c@test.com"
USER_ID = 2
SAVED_PATH = "/account/saved"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_results_visited(judge, trajectory, "visited_results_pediatrician_search", {"q": r"pediatric", "loc": NEWARK}, {"sids": "9", "loc": NEWARK})
    check_visited_profile(judge, trajectory, SLUG)
    check_visited_path(judge, trajectory, "visited_saved_providers_page", SAVED_PATH)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [("/login", {}), ("/results", {}), (profile_path_pattern(SLUG), {}), (SAVED_PATH, {})])
    judge.check("answer_confirms_saved", contains_any(answer, ("Castellano", "saved", "appears", "listed")), f"answer={answer!r}")
    added, removed = saved_delta(initial_db, after_db, USER_ID)
    judge.check("new_saved_row_belongs_to_bob", added == {DOCTOR_ID} and not removed, f"expected added=[{DOCTOR_ID}] removed=[]; observed added={sorted(added)!r} removed={sorted(removed)!r}")
    check_exact_delta(judge, initial_db, after_db, "saved_providers", added=1)
    check_tables_unchanged(judge, initial_db, after_db, ("users", "appointment_requests", "user_reviews"))


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
