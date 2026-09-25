#!/usr/bin/env python3
"""Verify OhioMeansJobs--0.

Find the nurse aide job in Findlay posted by Blanchard Valley Regional Health
Center; report its exact job title, job types and education level in its
summary, its reference code, its posted date and the sign-on-bonus mention;
then check the employer page for the total posting count, how many were
posted that same date and the title of the other one; open that other job and
report its salary range and whether it offers part-time.

Frozen ground truth (seed DB): job 6931551303 "Nurse Aide, STNA (FT, PT, PRN)"
at Blanchard Valley Regional Health Center, Findlay, OH — job types Full-Time +
Permanent, education "Bachelor's degree", reference code "NA", posted
2026-09-24, description mentions "Sign On Bonus Eligible!". The employer has 8
postings, 2 posted 2026-09-24; the other same-date Findlay job is "Res Care
Nurse (Heights) - PRN" (6931520233) — salary band "High Income Jobs
($80K-$99K)", offers Part-Time. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_date,
                        contains_phrase, final_answer, job_by_id,
                        navigated_jobs_search, navigated_job_detail,
                        run_verifier)

TASK_ID = "OhioMeansJobs--0"
JOB_ID = "6931551303"
OTHER_SAME_DATE_ID = "6931520233"
COMPANY_SLUG = "blanchard-valley-regional-health-center"
COMPANY_TOTAL = 8
SAME_DATE_COUNT = 2
OTHER_SAME_DATE = "Res Care Nurse (Heights) - PRN"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: job-search with the task's query, the target job detail,
    # and the employer profile page
    judge.check("visited_jobs_search_nurse_aide_findlay",
                navigated_jobs_search(traj, tjt=["nurse aide", "nurse+aide", "nurse%20aide"]),
                "required: /jobs/search with tjt=nurse aide (Findlay target)")
    judge.check("visited_target_job_detail", navigated_job_detail(traj, JOB_ID),
                f"required: /jobs/view/{JOB_ID}")
    check_visited_path(judge, traj, "visited_company_page", f"/jobs/company/{COMPANY_SLUG}")
    # answer facts (all hardcoded ground truth from the frozen seed)
    judge.check("answer_job_title", contains_phrase(answer, "Nurse Aide, STNA (FT, PT, PRN)"),
                "expected exact title 'Nurse Aide, STNA (FT, PT, PRN)'")
    judge.check("answer_job_types", contains_phrase(answer, "Full-Time")
                and contains_phrase(answer, "Permanent"),
                "expected job types Full-Time and Permanent")
    judge.check("answer_ref_code_na",
                contains_phrase(answer, "NA") or contains_phrase(answer, "N/A"),
                "expected reference code NA (as shown on the detail page)")
    judge.check("answer_education", contains_phrase(answer, "Bachelor's degree"),
                "expected education level Bachelor's degree in the job summary")
    judge.check("answer_posted_date", contains_date(answer, "2026-09-24"),
                "expected posted date 2026-09-24")
    judge.check("answer_sign_on_bonus",
                contains_phrase(answer, "Sign On Bonus") or contains_phrase(answer, "sign-on bonus"),
                "expected the sign-on bonus mention from the description")
    judge.check("answer_company_total", contains_count(answer, COMPANY_TOTAL),
                f"expected employer posting count {COMPANY_TOTAL}")
    judge.check("answer_same_date_count", contains_count(answer, SAME_DATE_COUNT),
                f"expected {SAME_DATE_COUNT} postings by that employer on the same date")
    judge.check("answer_other_same_date_job", contains_phrase(answer, OTHER_SAME_DATE),
                f"expected the other same-date Findlay job '{OTHER_SAME_DATE}'")
    judge.check("visited_other_same_date_detail",
                navigated_job_detail(traj, OTHER_SAME_DATE_ID),
                f"required: /jobs/view/{OTHER_SAME_DATE_ID} (the other same-date job)")
    judge.check("answer_other_salary_range",
                contains_phrase(answer, "$80K-$99K") or contains_phrase(answer, "80k-99k"),
                "expected the other job's salary range High Income Jobs ($80K-$99K)")
    judge.check("answer_other_part_time", contains_phrase(answer, "Part-Time"),
                "expected the other job to offer Part-Time")
    # seed sanity: the target job exists with the frozen facts
    job = job_by_id(initial_db, JOB_ID)
    judge.check("seed_job_facts", job is not None and job["company"] == "Blanchard Valley "
                "Regional Health Center" and job["posted_date"] == "2026-09-24",
                f"seed job row: {job['title'] if job else None!r}")
    # read-only task: nothing may change
    from verify_lib import check_signed_in_as, db_query
    check_signed_in_as(judge, traj, 'alice.j@test.com')
    judge.check('nurse_aide_saved', bool(db_query(after_db, "SELECT * FROM saved_jobs s JOIN jobs j ON j.id=s.job_id WHERE s.user_id=1 AND j.jobid='6931551303'")), 'requested opening saved')


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
