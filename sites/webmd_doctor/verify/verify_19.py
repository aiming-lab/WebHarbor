#!/usr/bin/env python3
"""Verify WebMD Doctor--19: Register a new account; Neurologists near Newark with virtual visits; save Dr. Monica Carrington; report her NPI (stateful).

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
    check_visited_before,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_npi,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    new_table_rows,
    new_user_rows,
    NEWARK,
    normalize_text,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    signup_email,
    user_emails,
)


TASK_ID = "WebMD Doctor--19"
SLUG = "monica-carrington-62f5d8a2"
DOCTOR_ID = 68
NPI = "1074536057"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_signup_page", "/signup")
    check_results_visited(
        judge, trajectory, "visited_virtual_neurologist_results",
        {"q": r"neurolog", "isvirtualvisit": True, "loc": NEWARK},
        {"sids": "4", "isvirtualvisit": True, "loc": NEWARK},
        {"q": r"(?=.*neurolog)(?=.*(?:virtual|telehealth|video visit))", "loc": NEWARK},
    )
    check_visited_profile(judge, trajectory, SLUG)
    check_paths_in_order(judge, trajectory, "workflow_in_order", [("/signup", {}), ("/results", {}), (profile_path_pattern(SLUG), {})])
    check_visited_before(
        judge, trajectory, "qualifying_results_precede_profile", "/results", profile_path_pattern(SLUG),
        before_params=[
            {"q": r"neurolog", "isvirtualvisit": True, "loc": NEWARK},
            {"sids": "4", "isvirtualvisit": True, "loc": NEWARK},
            {"q": r"(?=.*neurolog)(?=.*(?:virtual|telehealth|video visit))", "loc": NEWARK},
        ],
    )
    typed_email = signup_email(trajectory)
    check_exact_delta(judge, initial_db, after_db, "users", added=1)
    new_users = new_user_rows(initial_db, after_db)
    user = new_users[0] if len(new_users) == 1 else {}
    judge.check("new_user_email_matches_signup_input", bool(typed_email) and normalize_text(user.get("email")) == typed_email, f"typed_on_signup={typed_email!r}, new_user_email={user.get('email')!r}")
    judge.check("new_user_is_not_a_seed_account", bool(user) and normalize_text(user.get("email")) not in user_emails(initial_db), f"new_user_email={user.get('email')!r}")
    check_exact_delta(judge, initial_db, after_db, "saved_providers", added=1)
    new_saved = new_table_rows(initial_db, after_db, "saved_providers")
    saved = new_saved[0] if len(new_saved) == 1 else {}
    judge.check("new_saved_row_belongs_to_new_user", bool(user) and saved.get("user_id") == user.get("id"), f"new_user_id={user.get('id')!r}, row={saved!r}")
    judge.check("new_saved_row_is_for_target", saved.get("doctor_id") == DOCTOR_ID, f"expected_doctor_id={DOCTOR_ID}, row={saved!r}")
    judge.check("answer_has_npi", contains_npi(answer, NPI), f"expected={NPI!r}, answer={answer!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("appointment_requests", "user_reviews"))


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
