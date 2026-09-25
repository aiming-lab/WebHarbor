#!/usr/bin/env python3
"""Verify OhioMeansJobs--9.

Find the State of Ohio jobs page and report how many state agencies are shown;
search the board for Government industry jobs sorted by date, open the most
recent one, and report its exact title, employer, city, posted date, salary
range, and whether it is full-time or part-time; open the next-newest
Government job and report its title and city; finally visit that employer's
company page and report how many job postings it currently lists.

Frozen ground truth (seed DB): 37 state agencies. Government industry (code
92) has 6 jobs; date-sorted (posted_date, jobid desc) the most recent is
'Paramedic' @ Cincinnati Children's Hospital Medical Center, Cincinnati, OH,
posted 2026-09-23, salary band 2 = 'Middle Income Jobs ($30K-$49K)', job types
Full-Time + Part-Time + Permanent. The next-newest is 'Paramedic - Liberty
ED' @ Cincinnati Children's Hospital Medical Center, Liberty Township, OH
(6931749896). The employer's company page lists 11 active job postings.
Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_date,
                        contains_phrase, final_answer, navigated_jobs_search,
                        navigated_job_detail, run_verifier)

TASK_ID = "OhioMeansJobs--9"
AGENCIES = 37
GOV_JOB_ID = "6931751154"
NEXT_GOV_JOB_ID = "6931749896"
COMPANY_SLUG = "cincinnati-children-s-hospital-medical-center"
COMPANY_POSTINGS = 11


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_state_jobs", "/job-seekers/find-a-job/state-jobs")
    judge.check("visited_gov_industry_search",
                navigated_jobs_search(traj, omjindustry=["92"]),
                "required: /jobs/search with omjindustry=92 (Government facet)")
    judge.check("visited_most_recent_gov_job", navigated_job_detail(traj, GOV_JOB_ID),
                f"required: /jobs/view/{GOV_JOB_ID} (Paramedic, most recent Government job)")
    # answer facts
    judge.check("answer_agency_count", contains_count(answer, AGENCIES),
                f"expected {AGENCIES} state agencies")
    judge.check("answer_title", contains_phrase(answer, "Paramedic"),
                "expected 'Paramedic'")
    judge.check("answer_employer", contains_phrase(answer, "Cincinnati Children"),
                "expected employer Cincinnati Children's Hospital Medical Center")
    judge.check("answer_city", contains_phrase(answer, "Cincinnati"),
                "expected city Cincinnati")
    judge.check("answer_posted", contains_date(answer, "2026-09-23"),
                "expected posted 2026-09-23")
    judge.check("answer_salary_range",
                contains_phrase(answer, "$30K-$49K") or contains_phrase(answer, "30k-49k"),
                "expected salary range Middle Income Jobs ($30K-$49K)")
    judge.check("answer_full_time", contains_phrase(answer, "Full-Time"),
                "expected Full-Time among the job types")
    judge.check("answer_part_time", contains_phrase(answer, "Part-Time"),
                "expected Part-Time among the job types (the job lists both)")
    judge.check("visited_next_newest_gov_job", navigated_job_detail(traj, NEXT_GOV_JOB_ID),
                f"required: /jobs/view/{NEXT_GOV_JOB_ID} (the next-newest Government job)")
    judge.check("answer_next_gov_title", contains_phrase(answer, "Paramedic - Liberty ED"),
                "expected the next-newest Government job 'Paramedic - Liberty ED'")
    judge.check("answer_next_gov_city", contains_phrase(answer, "Liberty Township"),
                "expected the next-newest Government job city Liberty Township")
    check_visited_path(judge, traj, "visited_company_page", f"/jobs/company/{COMPANY_SLUG}")
    judge.check("answer_company_postings", contains_count(answer, COMPANY_POSTINGS),
                f"expected the employer's company page to list {COMPANY_POSTINGS} job postings")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
