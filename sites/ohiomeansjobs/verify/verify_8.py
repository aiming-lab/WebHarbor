#!/usr/bin/env python3
"""Verify OhioMeansJobs--8.

Find the OhioMeansJobs Center serving Ottawa County (name + street address),
the center serving Franklin County (street address), and the center serving
Cuyahoga County (street address); report the total number of center locations;
then search the job board for jobs within 20 miles of the city where the
Cuyahoga County center is located and report how many jobs appear and the
title and employer of the newest one.

Frozen ground truth (seed DB): Ottawa County → 'Ottawa County', 8043 W. State
Route 163, Suite 200, Oak Harbor, OH 43449; Franklin County →
'Columbus-Franklin County', 1111 E. Broad St., Columbus, OH 43205; Cuyahoga
County → 'Cleveland-Cuyahoga County', 1975 E. 61st Street, Cleveland, Ohio
44103 (city: Cleveland); 89 total center locations. Jobs within 20 miles of
Cleveland = 15; date-sorted newest = 'Staff Traffic Engineer' @ Langan
Engineering & Environmental Services (6930596393, posted 2026-09-24).
Read-only task.
"""
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
    judge.check("visited_ottawa_filter", any("county=Ottawa" in u for u in urls),
                "required: local-help with county=Ottawa")
    judge.check("visited_franklin_filter", any("county=Franklin" in u for u in urls),
                "required: local-help with county=Franklin")
    judge.check("visited_cuyahoga_filter", any("county=Cuyahoga" in u for u in urls),
                "required: local-help with county=Cuyahoga")
    # answer facts
    judge.check("answer_ottawa_name", contains_phrase(answer, "Ottawa County"),
                "expected the Ottawa County center name")
    judge.check("answer_ottawa_address",
                contains_phrase(answer, "8043 W. State Route 163"),
                "expected '8043 W. State Route 163, Suite 200, Oak Harbor, OH 43449'")
    judge.check("answer_franklin_address", contains_phrase(answer, "1111 E. Broad St."),
                "expected '1111 E. Broad St., Columbus, OH 43205'")
    judge.check("answer_cuyahoga_address", contains_phrase(answer, "1975 E. 61st Street"),
                "expected '1975 E. 61st Street, Cleveland, Ohio 44103'")
    judge.check("answer_total_centers", contains_count(answer, TOTAL_CENTERS),
                f"expected {TOTAL_CENTERS} total center locations")
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
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
