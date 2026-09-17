#!/usr/bin/env python3
"""Verify Walmart Careers--15: David signs in, updates city/state, opens My applications, reports his existing confirmation number (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_path,
    contains_confirmation_number,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
    rows_unchanged_except,
    user_id_for_email,
    user_profile,
)


TASK_ID = "Walmart Careers--15"
EMAIL = "david.k@test.com"
CITY = "Rogers"
STATE = "AR"
CONFIRMATION_NO = "WMC-000004"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_visited_path(judge, trajectory, "visited_account_edit_page", "/account/edit")
    check_visited_path(judge, trajectory, "visited_applications_page", "/candidate-home/applications")
    from verify_lib import check_paths_in_order
    check_paths_in_order(
        judge, trajectory, "workflow_in_order",
        [("/login", {}), ("/account/edit", {}), ("/candidate-home/applications", {})],
    )
    judge.check(
        "answer_has_existing_confirmation_number",
        contains_confirmation_number(answer, CONFIRMATION_NO),
        f"expected={CONFIRMATION_NO!r}, answer={answer!r}",
    )
    initial_profile = user_profile(initial_db, EMAIL) or {}
    judge.check(
        "initial_profile_requires_update",
        str(initial_profile.get("city") or "").casefold() != CITY.casefold()
        or str(initial_profile.get("state") or "").upper() != STATE,
        f"initial_city={initial_profile.get('city')!r}, initial_state={initial_profile.get('state')!r}",
    )
    profile = user_profile(after_db, EMAIL) or {}
    judge.check(
        "profile_city_and_state_updated",
        str(profile.get("city") or "").casefold() == CITY.casefold()
        and str(profile.get("state") or "").upper() == STATE,
        f"expected_city={CITY!r}, expected_state={STATE!r}, "
        f"after_city={profile.get('city')!r}, after_state={profile.get('state')!r}",
    )
    david_id = user_id_for_email(initial_db, EMAIL)
    judge.check(
        "other_users_unchanged",
        david_id is not None and rows_unchanged_except(initial_db, after_db, "users", [david_id]),
        f"excluded_user_id={david_id!r}",
    )
    from verify_lib import table_delta
    delta = table_delta(initial_db, after_db, "users")
    exact = False
    if len(delta["changed"]) == 1 and not delta["added"] and not delta["removed"]:
        before_row, after_row = delta["changed"][0]
        exact = (
            before_row[0] == david_id == after_row[0]
            and before_row[:7] == after_row[:7]
            and before_row[9:] == after_row[9:]
            and str(after_row[7]).casefold() == CITY.casefold()
            and str(after_row[8]).upper() == STATE
        )
    judge.check("profile_exact_delta", exact, f"delta={delta!r}")
    check_tables_unchanged(judge, initial_db, after_db, ("saved_jobs", "applications"))


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
