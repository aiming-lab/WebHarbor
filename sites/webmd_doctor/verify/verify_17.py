#!/usr/bin/env python3
"""Verify WebMD Doctor--17: Carol signs in, requests a New Patient appointment with Dr. Sarah Keller at the named office on Mon Sep 14 10:30 AM; reports the reference (stateful).

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
    contains_reference,
    extract_references,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    new_table_rows,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    rows_where,
)


TASK_ID = "WebMD Doctor--17"
SLUG = "sarah-keller-f85bed81"
DOCTOR_ID = 22
EMAIL = "carol.d@test.com"
USER_ID = 3
LOCATION_ID = 32  # Riverfront Heart & Vascular - Wellness Center (the non-primary office)
PATIENT_TYPE = "New Patient"
SLOT_DATE = "2026-09-14"
SLOT_TIME = "10:30 AM"
BOOKING_PATH = f"/doctor/{SLUG}/bookappointment"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_visited_profile(judge, trajectory, SLUG)
    check_visited_path(judge, trajectory, "visited_booking_page", BOOKING_PATH)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [("/login", {}), (profile_path_pattern(SLUG), {}), (BOOKING_PATH, {})])
    judge.check("initial_has_no_carol_request_for_target", not rows_where(initial_db, "appointment_requests", user_id=USER_ID, doctor_id=DOCTOR_ID), f"user_id={USER_ID}, doctor_id={DOCTOR_ID}")
    new_rows = new_table_rows(initial_db, after_db, "appointment_requests")
    judge.check("exactly_one_new_request", len(new_rows) == 1, f"new_rows={new_rows!r}")
    row = new_rows[0] if len(new_rows) == 1 else {}
    judge.check("new_request_belongs_to_carol", row.get("user_id") == USER_ID, f"expected_user_id={USER_ID}, row={row!r}")
    judge.check("new_request_is_for_target", row.get("doctor_id") == DOCTOR_ID, f"expected_doctor_id={DOCTOR_ID}, row={row!r}")
    judge.check("new_request_at_named_office", row.get("location_id") == LOCATION_ID, f"expected_location_id={LOCATION_ID}, row={row!r}")
    judge.check("new_request_is_new_patient", row.get("patient_type") == PATIENT_TYPE, f"expected={PATIENT_TYPE!r}, row={row!r}")
    judge.check(
        "new_request_slot_matches",
        str(row.get("slot_date") or "").startswith(SLOT_DATE) and str(row.get("slot_time") or "").strip().upper() == SLOT_TIME,
        f"expected={SLOT_DATE} {SLOT_TIME}, row={row!r}",
    )
    reference = str(row.get("reference") or "")
    judge.check("answer_has_matching_reference", bool(reference) and contains_reference(answer, reference), f"row_reference={reference!r}, answer={answer!r}")
    judge.check("answer_has_no_other_reference", extract_references(answer) <= ({reference} if reference else set()), f"answer_references={sorted(extract_references(answer))!r}")
    check_exact_delta(judge, initial_db, after_db, "appointment_requests", added=1)
    check_tables_unchanged(judge, initial_db, after_db, ("users", "saved_providers", "user_reviews"))


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
