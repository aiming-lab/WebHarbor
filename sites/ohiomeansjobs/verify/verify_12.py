#!/usr/bin/env python3
"""Verify OhioMeansJobs--12.

Find remote-friendly data analyst jobs on the board and report how many
match. Open the Senior Data Analyst job at Steris Corporation and report its
exact title, city, posted date, job types, and the salary range mentioned in
its description. Then open the result listed immediately after it and report
that job's title, employer, and posted date. Finally, report the title,
employer, and posted date of the newest matching result of all.

Frozen ground truth (seed DB): 'data analyst' + Remote-friendly = 10 results
date-sorted. The Steris job 6931749872 'Senior Data Analyst - Distribution and
Transportation' (Mentor, OH, posted 2026-09-23, Full-Time + Permanent,
description salary $85,000 - $110,000) is listed after 'Sales Instructor' @
Vertiv (2026-09-24). The result listed immediately after it is 'Experienced
Registered Nurse, RN, Nurse Helpline, Part-Time' @ Cincinnati Children's
Hospital Medical Center (6931641205, posted 2026-09-23). The newest matching
result of all is 'Sales Instructor' @ Vertiv Corporation (6930894447,
2026-09-24). Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        contains_amount, contains_count, contains_date,
                        contains_phrase, final_answer, navigated_jobs_search,
                        navigated_job_detail, run_verifier)

TASK_ID = "OhioMeansJobs--12"
COUNT = 10
STERIS_ID = "6931749872"
AFTER_STERIS_ID = "6931641205"
NEWEST_ID = "6930894447"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_remote_data_analyst_search",
                navigated_jobs_search(traj, tjt=["data analyst", "data+analyst", "data%20analyst"],
                                      remote=["1", "on", "true"]),
                "required: /jobs/search with tjt=data analyst + remote filter")
    judge.check("visited_steris_detail", navigated_job_detail(traj, STERIS_ID),
                f"required: /jobs/view/{STERIS_ID}")
    judge.check("visited_after_steris_detail", navigated_job_detail(traj, AFTER_STERIS_ID),
                f"required: /jobs/view/{AFTER_STERIS_ID} (the result listed immediately after Steris)")
    judge.check("visited_newest_detail", navigated_job_detail(traj, NEWEST_ID),
                f"required: /jobs/view/{NEWEST_ID} (the newest matching result of all)")
    # answer facts
    judge.check("answer_count", contains_count(answer, COUNT),
                f"expected {COUNT} remote data-analyst matches")
    judge.check("answer_steris_title",
                contains_phrase(answer, "Senior Data Analyst - Distribution and Transportation"),
                "expected 'Senior Data Analyst - Distribution and Transportation'")
    judge.check("answer_steris_city", contains_phrase(answer, "Mentor"),
                "expected city Mentor, OH")
    judge.check("answer_steris_posted", contains_date(answer, "2026-09-23"),
                "expected posted 2026-09-23")
    judge.check("answer_steris_types", contains_phrase(answer, "Full-Time")
                and contains_phrase(answer, "Permanent"),
                "expected job types Full-Time + Permanent")
    judge.check("answer_steris_salary",
                contains_amount(answer, 85000) and contains_amount(answer, 110000),
                "expected the description salary range $85,000 - $110,000")
    judge.check("answer_after_steris_title",
                contains_phrase(answer, "Nurse Helpline"),
                "expected the after-Steris result 'Experienced Registered Nurse, RN, Nurse "
                "Helpline, Part-Time'")
    judge.check("answer_after_steris_employer",
                contains_phrase(answer, "Cincinnati Children"),
                "expected the after-Steris employer Cincinnati Children's Hospital Medical Center")
    judge.check("answer_after_steris_posted", contains_date(answer, "2026-09-23"),
                "expected the after-Steris result posted 2026-09-23")
    judge.check("answer_newest_title", contains_phrase(answer, "Sales Instructor"),
                "expected the newest matching result 'Sales Instructor'")
    judge.check("answer_newest_employer", contains_phrase(answer, "Vertiv"),
                "expected the newest matching employer Vertiv Corporation")
    judge.check("answer_newest_posted", contains_date(answer, "2026-09-24"),
                "expected the newest matching result posted 2026-09-24")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
