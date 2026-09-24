#!/usr/bin/env python3
"""Verify OhioMeansJobs--7.

Log in as david.k@test.com, report the title and employer of his current top
SkillsMatch recommendation, add 'tax preparation' to his resume skills, keep
the resume active, save it, report the titles and employers of the top three
SkillsMatch recommendations now shown, open the one located in Dover, Ohio
(posted date, job types, education level), and open the top recommended job
(its posted date).

Frozen ground truth (seed DB + live site logic, tie order = rowid ASC):
after adding 'tax preparation' to david's skills (quickbooks, excel,
reconciliation, payroll, accounts payable, gaap + tax preparation) the top
three SkillsMatch recommendations are
  1. 'Senior Accountant, Grants and General Ledger' @ The College of Wooster
  2. 'Customer Service Coordinator' @ CoolSeal Inc.
  3. 'Application Engineer - AC Power, Hyperscale' @ Vertiv Corporation
(the same job is also the current top recommendation before the update).
The Dover, OH one is #3 (job 6930560403): posted 2026-09-24, Full-Time +
Temporary, education "Bachelor's degree". The top recommended job is
6931261515, posted 2026-09-23. Stateful task: allowed delta = resumes
(david's row: skills gain 'tax preparation', active stays true);
nothing else.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_date, contains_phrase, final_answer,
                        navigated_job_detail, resume_of, run_verifier,
                        SEED_USERS)

TASK_ID = "OhioMeansJobs--7"
EMAIL = "david.k@test.com"
DAVID_ID = SEED_USERS[EMAIL][0]
TOP_RECS = ("Senior Accountant, Grants and General Ledger",
            "Customer Service Coordinator",
            "Application Engineer - AC Power, Hyperscale")
REC_EMPLOYERS = ("The College of Wooster", "CoolSeal Inc.", "Vertiv Corporation")
DOVER_ID = "6930560403"
TOP_JOB_ID = "6931261515"
STATEFUL_TABLES = ("resumes",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_resume", "/account/resume")
    judge.check("visited_dover_detail", navigated_job_detail(traj, DOVER_ID),
                f"required: /jobs/view/{DOVER_ID} (the Dover, OH recommendation)")
    judge.check("visited_top_rec_detail", navigated_job_detail(traj, TOP_JOB_ID),
                f"required: /jobs/view/{TOP_JOB_ID} (the top recommended job)")
    # answer facts: all three recommended titles with employers
    for rec in TOP_RECS:
        judge.check(f"answer_rec_{rec[:24]}", contains_phrase(answer, rec),
                    f"expected recommendation '{rec}'")
    for emp in REC_EMPLOYERS:
        judge.check(f"answer_employer_{emp[:20]}", contains_phrase(answer, emp),
                    f"expected employer '{emp}' alongside the recommendation titles")
    judge.check("answer_dover_posted", contains_date(answer, "2026-09-24"),
                "expected the Dover, OH job posted 2026-09-24")
    judge.check("answer_dover_types",
                contains_phrase(answer, "Full-Time") and contains_phrase(answer, "Temporary"),
                "expected the Dover, OH job types Full-Time + Temporary")
    judge.check("answer_dover_education", contains_phrase(answer, "Bachelor's degree"),
                "expected the Dover, OH job education Bachelor's degree")
    judge.check("answer_top_rec_posted", contains_date(answer, "2026-09-23"),
                "expected the top recommended job posted 2026-09-23")
    # DB after-state: david's resume row gains 'tax preparation', stays active
    seed_resume = resume_of(initial_db, DAVID_ID)
    after_resume = resume_of(after_db, DAVID_ID)
    judge.check("resume_skills_gained_tax_preparation",
                after_resume is not None and "tax preparation" in (after_resume["skills"] or "").lower()
                and "tax preparation" not in (seed_resume["skills"] or "").lower(),
                f"skills before={seed_resume['skills']!r} after={after_resume['skills'] if after_resume else None!r}")
    judge.check("resume_active", after_resume is not None and bool(after_resume["active"]),
                f"active={after_resume['active'] if after_resume else None!r}")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
