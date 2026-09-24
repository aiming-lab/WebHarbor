#!/usr/bin/env python3
"""Verify OhioMeansJobs--4.

Log in as bob.c@test.com. He has three saved jobs. Remove the saved job whose
title mentions being a lift driver, then apply to the remaining saved job
posted most recently, and report that job's exact title and city.

Frozen ground truth (seed DB): bob's saved jobs are
  - 'Material Handler, Warehouse' @ ICU Medical, Dublin, OH (2026-09-23)
  - 'Forklift operator - 3rd shift' @ DHL eCommerce, Stow, OH (2026-09-22)
  - 'Union Production Operator - Forklift Operator | Lift Driver' @ DuBois
    Chemicals, Cincinnati, OH (2026-09-22)
The lift-driver job (6930717794) must be removed; the most recent remaining is
'Material Handler, Warehouse' (6928198981, Dublin) which must be applied to.
Stateful task: allowed delta = saved_jobs -1 (bob → 6930717794),
applications +1 (bob → Material Handler job); nothing else.
"""
from verify_lib import (Judge, added_applications, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        job_by_id, navigated_job_detail, removed_saved_jobs,
                        run_verifier)

TASK_ID = "OhioMeansJobs--4"
EMAIL = "bob.c@test.com"
LIFT_DRIVER_ID = "6930717794"
TARGET_ID = "6928198981"
STATEFUL_TABLES = ("saved_jobs", "applications")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_saved_jobs", "/account/saved-jobs")
    judge.check("removed_lift_driver_opened", navigated_job_detail(traj, LIFT_DRIVER_ID),
                f"required: /jobs/view/{LIFT_DRIVER_ID} (the lift-driver job to remove)")
    judge.check("applied_target_opened", navigated_job_detail(traj, TARGET_ID),
                f"required: /jobs/view/{TARGET_ID} (the most recent remaining saved job)")
    # answer facts
    judge.check("answer_title", contains_phrase(answer, "Material Handler, Warehouse"),
                "expected 'Material Handler, Warehouse'")
    judge.check("answer_city", contains_phrase(answer, "Dublin"),
                "expected city Dublin, OH")
    # DB after-state
    removed = removed_saved_jobs(after_db, initial_db)
    judge.check("lift_driver_removed", len(removed) == 1,
                f"removed_saved_jobs={[(r['user_id'], r['job_id']) for r in removed]!r}")
    if removed:
        lift = job_by_id(initial_db, LIFT_DRIVER_ID)
        judge.check("removed_exactly_lift_driver",
                    removed[0]["user_id"] == 2 and removed[0]["job_id"] == lift["id"],
                    f"removed row user={removed[0]['user_id']}, job={removed[0]['job_id']}")
    apps = added_applications(after_db, initial_db)
    judge.check("one_application_added", len(apps) == 1, f"added={apps!r}")
    if apps:
        a = apps[0]
        target = job_by_id(after_db, TARGET_ID)
        judge.check("application_for_material_handler",
                    a["job_id"] == target["id"] and a["user_id"] == 2,
                    f"job_id={a['job_id']}, user_id={a['user_id']} (bob=2)")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
