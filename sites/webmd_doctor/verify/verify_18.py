#!/usr/bin/env python3
"""Verify WebMD Doctor--18: David signs in, leaves a 4-star review with the quoted text on Dr. Tariq Huang, confirms Pending review (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_ended_on_profile,
    check_exact_delta,
    check_paths_in_order,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_profile,
    contains_any,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    new_table_rows,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    review_text_matches,
    rows_where,
)


TASK_ID = "WebMD Doctor--18"
SLUG = "tariq-huang-c8120504"
DOCTOR_ID = 18
EMAIL = "david.k@test.com"
USER_ID = 4
RATING = 4
TEXT = "Short wait and a clear explanation of my treatment options."
STATUS = "Pending review"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_visited_profile(judge, trajectory, SLUG)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [("/login", {}), (profile_path_pattern(SLUG), {})])
    check_ended_on_profile(judge, trajectory, SLUG)
    judge.check("initial_has_no_david_review_for_target", not rows_where(initial_db, "user_reviews", user_id=USER_ID, doctor_id=DOCTOR_ID), f"user_id={USER_ID}, doctor_id={DOCTOR_ID}")
    check_exact_delta(judge, initial_db, after_db, "user_reviews", added=1)
    new_rows = new_table_rows(initial_db, after_db, "user_reviews")
    row = new_rows[0] if len(new_rows) == 1 else {}
    judge.check("new_review_belongs_to_david", row.get("user_id") == USER_ID, f"expected_user_id={USER_ID}, row={row!r}")
    judge.check("new_review_is_for_target", row.get("doctor_id") == DOCTOR_ID, f"expected_doctor_id={DOCTOR_ID}, row={row!r}")
    judge.check("new_review_rating_is_4", row.get("rating") == RATING, f"expected={RATING}, row={row!r}")
    judge.check("new_review_text_matches", review_text_matches(row.get("text"), TEXT), f"expected={TEXT!r}, row_text={row.get('text')!r}")
    judge.check("new_review_status_pending", str(row.get("status") or "").casefold() == STATUS.casefold(), f"expected={STATUS!r}, row={row!r}")
    judge.check("answer_confirms_pending", contains_any(answer, ("pending",)), f"answer={answer!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("users", "saved_providers", "appointment_requests"))


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
