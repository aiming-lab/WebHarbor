#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, navigated_job_detail,
                        navigated_jobs_search, run_verifier, trajectory_urls)

TASK_ID = "OhioMeansJobs--8"
LOCAL_HELP = "/job-seekers/find-a-job/local-help"
TOTAL_CENTERS = 89
CLEVELAND_JOBS = 15
NEWEST_ID = "6930596393"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_local_help", LOCAL_HELP)
    urls = trajectory_urls(traj)
    judge.check("visited_cuyahoga_filter", any("county=Cuyahoga" in u for u in urls),
                "required: local-help with county=Cuyahoga")
    # answer facts
    judge.check("answer_cuyahoga_address", contains_phrase(answer, "1975 E. 61st Street"),
                "expected '1975 E. 61st Street, Cleveland, Ohio 44103'")
    judge.check("visited_cleveland_radius_search",
                navigated_jobs_search(traj, cnme=["Cleveland"], rad=["20"]),
                "required: /jobs/search with cnme=Cleveland & rad=20 (jobs within 20 miles of Cleveland)")
    judge.check("answer_cleveland_job_count", contains_count(answer, CLEVELAND_JOBS),
                f"expected {CLEVELAND_JOBS} jobs within 20 miles of Cleveland")
    judge.check("visited_newest_cleveland_job", navigated_job_detail(traj, NEWEST_ID),
                f"required: /jobs/view/{NEWEST_ID} (the newest Cleveland-area job)")
    judge.check("answer_newest_cleveland_title", contains_phrase(answer, "Staff Traffic Engineer"),
                "expected the newest Cleveland-area job 'Staff Traffic Engineer'")
    judge.check("answer_newest_cleveland_employer", contains_phrase(answer, "Langan"),
                "expected employer Langan Engineering & Environmental Services")
    from verify_lib import contains_date
    judge.check('center_name', contains_phrase(answer, 'Cleveland-Cuyahoga County'), 'center name')
    judge.check('newest_date', contains_date(answer, '2026-09-24'), 'newest posting date')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
