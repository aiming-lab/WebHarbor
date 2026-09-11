#!/usr/bin/env python3
"""Verify WebMD Doctor--8: Alice signs in; the only saved Dermatologist: residency, then remove it from Saved Providers (stateful).

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
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_institution,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    saved_delta,
    saved_doctor_ids,
)


TASK_ID = "WebMD Doctor--8"
SLUG = "adrian-navarro-b338ac81"
DOCTOR_ID = 5
EMAIL = "alice.j@test.com"
USER_ID = 1
SAVED_PATH = "/account/saved"
RESIDENCY = "Piedmont Atlantic Hospital"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_visited_path(judge, trajectory, "visited_saved_providers_page", SAVED_PATH)
    check_visited_profile(judge, trajectory, SLUG)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [("/login", {}), (SAVED_PATH, {}), (profile_path_pattern(SLUG), {})])
    judge.check("initial_alice_has_target_saved", DOCTOR_ID in saved_doctor_ids(initial_db, USER_ID), f"initial_saved={sorted(saved_doctor_ids(initial_db, USER_ID))!r}")
    judge.check("answer_has_residency", contains_institution(answer, RESIDENCY), f"expected={RESIDENCY!r}, answer={answer!r}")
    check_exact_delta(judge, initial_db, after_db, "saved_providers", removed=1)
    added, removed = saved_delta(initial_db, after_db, USER_ID)
    judge.check("removed_target_only", removed == {DOCTOR_ID} and not added, f"expected removed={{{DOCTOR_ID}}} added=set(); observed removed={sorted(removed)!r} added={sorted(added)!r}")
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
