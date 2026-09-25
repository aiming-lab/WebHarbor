#!/usr/bin/env python3
"""Verify OhioMeansJobs--3.

Log in as alice.j@test.com, apply to the CICU Nurse Practitioner opening at
Cincinnati Children's Hospital Medical Center attaching the med-surg cover
letter, report the education level listed in that job's summary, confirm the
application in the applications list, and report the job's reference code and
the application status shown.

Frozen ground truth (seed DB): CICU NP = job 6931749800, reference code "NA",
education level "Master's degree"; application status "Submitted"; alice's
med-surg letter is 'Med-Surg Nursing Cover Letter' (her letter id 1).
Stateful task: allowed delta = applications +1 (alice → CICU job,
cover_letter_id = 1); nothing else.
"""
from verify_lib import (Judge, added_applications, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        job_by_id, navigated_job_detail, navigated_jobs_search,
                        run_verifier)

TASK_ID = "OhioMeansJobs--3"
EMAIL = "alice.j@test.com"
JOB_ID = "6931749800"
STATEFUL_TABLES = ("applications",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_np_search",
                navigated_jobs_search(traj, tjt=["nurse practitioner", "nurse+practitioner"]),
                "required: /jobs/search with tjt=nurse practitioner")
    judge.check("visited_cicu_detail", navigated_job_detail(traj, JOB_ID),
                f"required: /jobs/view/{JOB_ID}")
    check_visited_path(judge, traj, "visited_applications", "/account/applications")
    # answer facts
    judge.check("answer_ref_code",
                contains_phrase(answer, "NA") or contains_phrase(answer, "N/A"),
                "expected the CICU job reference code NA")
    judge.check("answer_education", contains_phrase(answer, "Master's degree"),
                "expected the CICU job education level Master's degree")
    judge.check("answer_status", contains_phrase(answer, "Submitted"),
                "expected application status 'Submitted'")
    # DB after-state: exactly one new application for alice → CICU with the
    # med-surg letter attached
    apps = added_applications(after_db, initial_db)
    judge.check("one_application_added", len(apps) == 1, f"added={apps!r}")
    if apps:
        a = apps[0]
        job = job_by_id(after_db, JOB_ID)
        judge.check("application_for_cicu", a["job_id"] == job["id"],
                    f"job_id={a['job_id']} (expected CICU NP job id {job['id']})")
        judge.check("application_by_alice", a["user_id"] == 1,
                    f"user_id={a['user_id']} (alice must be user 1)")
        judge.check("application_status_submitted", a["status"] == "Submitted",
                    f"status={a['status']!r}")
        judge.check("application_med_surg_letter", a["cover_letter_id"] == 1,
                    f"cover_letter_id={a['cover_letter_id']!r} (Med-Surg Nursing Cover Letter = id 1)")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
