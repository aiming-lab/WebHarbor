#!/usr/bin/env python3
"""Verify OhioMeansJobs--2.

Register grad.2026@test.com, create the cover letter 'First Position Letter',
find the most recently posted receptionist job in Cincinnati, apply attaching
that letter, and report the job title, employer and confirmation number.

Frozen ground truth (seed DB): the newest Cincinnati receptionist job is
6928092839 "Part-Time Receptionist / Front Desk Coordinator" @ Beacon Hill
Staffing Group, LLC (posted 2026-09-19). The seed has 5 applications, so the
new one gets id 6 → confirmation "OMJ-6-2839" (jobid ends 2839). Stateful
task: allowed delta = users +1 (grad.2026@test.com), cover_letters +1 (First
Position Letter), applications +1 (user 5 → job 6928092839); nothing else.
"""
from verify_lib import (Judge, added_applications, added_users, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        cover_letters_of, final_answer, job_by_id, navigated_job_detail,
                        navigated_jobs_search, run_verifier, trajectory_urls)

TASK_ID = "OhioMeansJobs--2"
EMAIL = "grad.2026@test.com"
JOB_ID = "6928092839"
CONFIRMATION = "OMJ-6-2839"
STATEFUL_TABLES = ("users", "cover_letters", "applications")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: register, cover letters, receptionist search, job
    # detail, apply page
    check_visited_path(judge, traj, "visited_register", "/account/register")
    check_visited_path(judge, traj, "visited_cover_letters", "/account/cover-letters")
    judge.check("visited_receptionist_search",
                navigated_jobs_search(traj, tjt=["receptionist"], cnme=["Cincinnati"]),
                "required: /jobs/search with tjt=receptionist + Cincinnati")
    judge.check("visited_target_job", navigated_job_detail(traj, JOB_ID),
                f"required: /jobs/view/{JOB_ID}")
    judge.check("visited_apply_page",
                any("/jobs/apply/" in u for u in trajectory_urls(traj)),
                "required: /jobs/apply/<jobid>")
    # answer facts
    judge.check("answer_job_title",
                contains_phrase(answer, "Part-Time Receptionist / Front Desk Coordinator"),
                "expected 'Part-Time Receptionist / Front Desk Coordinator'")
    judge.check("answer_employer", contains_phrase(answer, "Beacon Hill"),
                "expected employer Beacon Hill Staffing Group, LLC")
    judge.check("answer_confirmation", contains_phrase(answer, CONFIRMATION),
                f"expected confirmation number {CONFIRMATION}")
    # DB after-state: exactly the allowed delta
    users = added_users(after_db, initial_db)
    judge.check("one_user_added", len(users) == 1
                and users[0]["email"].lower() == EMAIL,
                f"added_users={[u['email'] for u in users]!r}")
    apps = added_applications(after_db, initial_db)
    judge.check("one_application_added", len(apps) == 1,
                f"added_applications={apps!r}")
    if apps:
        a = apps[0]
        job = job_by_id(after_db, JOB_ID)
        judge.check("application_for_target_job",
                    a["job_id"] == job["id"] and a["status"] == "Submitted",
                    f"application job_id={a['job_id']}, status={a['status']!r}")
        judge.check("application_by_new_user", a["user_id"] == 5,
                    f"user_id={a['user_id']} (grad.2026@test.com must be user 5)")
        judge.check("application_attached_letter", a["cover_letter_id"] is not None,
                    f"cover_letter_id={a['cover_letter_id']!r} (must attach 'First Position Letter')")
    letters = cover_letters_of(after_db, 5)
    judge.check("cover_letter_created",
                any(l["name"] == "First Position Letter" for l in letters),
                f"letters={[l['name'] for l in letters]!r}")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
