#!/usr/bin/env python3
"""Verify Walmart Careers--14: Register a new account, then save the eCom Warehouse Worker posting at #9046 Marcy (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_tables_unchanged,
    check_trajectory_identity,
    check_visited_job_detail,
    check_visited_path,
    fail_closed,
    load_run,
    new_user_ids,
    parse_args,
    resolve_snapshots,
    saved_job_ids_by_user_id,
    user_ids,
)


TASK_ID = "Walmart Careers--14"
JOB_ID = "CP-9046-11274"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    from ground_truth import constants_for_task
    globals().update(constants_for_task(initial_db, int(TASK_ID.rsplit("--", 1)[1])))
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_visited_path(judge, trajectory, "visited_register_page", "/register")
    check_visited_job_detail(judge, trajectory, JOB_ID)
    from verify_lib import check_paths_in_order
    check_paths_in_order(
        judge, trajectory, "workflow_in_order", [("/register", {}), (f"/jobs/{JOB_ID}", {})]
    )
    fresh = new_user_ids(initial_db, after_db)
    judge.check("new_user_registered", len(fresh) == 1, f"new_user_ids={sorted(fresh)!r}")
    from verify_lib import new_user_emails, trajectory_last_email, trajectory_input_texts
    fresh_emails = new_user_emails(initial_db, after_db)
    judge.check(
        "registered_email_matches_trajectory",
        len(fresh_emails) == 1 and trajectory_last_email(trajectory) in fresh_emails,
        f"new_emails={sorted(fresh_emails)!r}, entered_email={trajectory_last_email(trajectory)!r}",
    )
    non_email_inputs = [value for value in trajectory_input_texts(trajectory) if "@" not in value]
    judge.check(
        "registration_password_entered",
        any(8 <= len(value) <= 256 for value in non_email_inputs),
        f"non_email_input_count={len(non_email_inputs)}",
    )
    savers = sorted(uid for uid in fresh if JOB_ID in saved_job_ids_by_user_id(after_db, uid))
    judge.check(
        "target_saved_by_new_user",
        len(savers) == 1 and saved_job_ids_by_user_id(after_db, savers[0]) == {JOB_ID},
        f"job_id={JOB_ID}, new_user_ids={sorted(fresh)!r}, new_users_with_target={savers!r}",
    )
    seeded_gainers = sorted(
        uid
        for uid in user_ids(initial_db)
        if JOB_ID in saved_job_ids_by_user_id(after_db, uid)
        and JOB_ID not in saved_job_ids_by_user_id(initial_db, uid)
    )
    judge.check(
        "no_seeded_user_gained_target",
        not seeded_gainers,
        f"seeded_users_that_gained_target={seeded_gainers!r}",
    )
    from verify_lib import table_delta
    user_delta = table_delta(initial_db, after_db, "users")
    saved_delta = table_delta(initial_db, after_db, "saved_jobs")
    new_id = next(iter(fresh)) if len(fresh) == 1 else None
    judge.check(
        "users_exact_delta",
        len(user_delta["added"]) == 1 and not user_delta["removed"] and not user_delta["changed"]
        and user_delta["added"][0][0] == new_id,
        f"delta={user_delta!r}",
    )
    judge.check(
        "saved_jobs_exact_delta",
        len(saved_delta["added"]) == 1 and not saved_delta["removed"] and not saved_delta["changed"]
        and saved_delta["added"][0][1:3] == (new_id, JOB_ID),
        f"delta={saved_delta!r}",
    )
    check_tables_unchanged(judge, initial_db, after_db, ("applications",))


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
