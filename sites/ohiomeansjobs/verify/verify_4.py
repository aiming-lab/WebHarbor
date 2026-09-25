#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (Judge, added_applications, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        job_by_id, navigated_job_detail, removed_saved_jobs,
                        run_verifier)

TASK_ID = "OhioMeansJobs--4"
EMAIL = "bob.c@test.com"
LIFT_DRIVER_ID = "6930717794"
TARGET_ID = "6928198981"
STATEFUL_TABLES = ("applications",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_saved_jobs", "/account/saved-jobs")
    judge.check("applied_target_opened", navigated_job_detail(traj, TARGET_ID),
                f"required: /jobs/view/{TARGET_ID} (the most recent remaining saved job)")
    # answer facts
    judge.check("answer_title", contains_phrase(answer, "Material Handler, Warehouse"),
                "expected 'Material Handler, Warehouse'")
    judge.check("answer_city", contains_phrase(answer, "Dublin"),
                "expected city Dublin, OH")
    # DB after-state
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
