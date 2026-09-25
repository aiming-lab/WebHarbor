#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        contains_count, contains_count_near, contains_date,
                        contains_phrase, final_answer, normalize_text,
                        navigated_jobs_search, navigated_job_detail, run_verifier)

TASK_ID = "OhioMeansJobs--1"
NURSE_COUNT = 12
MECHANIC_ID = "6929453642"
CICU_ID = "6931749800"
PART_TIME_COUNT = 2


def _all_indices(haystack, needle):
    out, i = [], 0
    while True:
        j = haystack.find(needle, i)
        if j == -1:
            return out
        out.append(j)
        i = j + 1


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: nurse search, six-figure narrowing, both detail pages
    judge.check("visited_nurse_search", navigated_jobs_search(traj, tjt=["nurse"]),
                "required: /jobs/search with tjt=nurse")
    judge.check("visited_six_figure_search",
                navigated_jobs_search(traj, tjt=["nurse"], saltyp=["5"]),
                "required: /jobs/search with tjt=nurse&saltyp=5 (Six Figure facet)")
    judge.check("visited_findlay_health_center_job", navigated_job_detail(traj, MECHANIC_ID),
                f"required: /jobs/view/{MECHANIC_ID} (MECHANIC II at Blanchard Valley, Findlay)")
    judge.check("visited_childrens_hospital_job", navigated_job_detail(traj, CICU_ID),
                f"required: /jobs/view/{CICU_ID} (CICU Nurse Practitioner at Cincinnati Children's)")
    # answer facts
    judge.check("answer_nurse_count", contains_count(answer, NURSE_COUNT),
                f"expected {NURSE_COUNT} nurse results")
    judge.check("answer_two_six_figure", contains_count(answer, 2),
                "expected 2 six-figure nurse results")
    judge.check("answer_mechanic_title", contains_phrase(answer, "MECHANIC II"),
                "expected 'MECHANIC II - Full Time, 2nd Shift'")
    judge.check("answer_mechanic_employer", contains_phrase(answer, "Blanchard Valley"),
                "expected employer Blanchard Valley Regional Health Center")
    judge.check("answer_cicu_title", contains_phrase(answer, "CICU Nurse Practitioner"),
                "expected 'CICU Nurse Practitioner'")
    judge.check("answer_cicu_employer", contains_phrase(answer, "Cincinnati Children"),
                "expected employer Cincinnati Children's Hospital Medical Center")
    judge.check("answer_mechanic_posted", contains_date(answer, "2026-09-23"),
                "expected MECHANIC II posted 2026-09-23")
    judge.check("answer_mechanic_types", contains_phrase(answer, "Full-Time")
                and contains_phrase(answer, "Permanent"),
                "expected MECHANIC II job types Full-Time + Permanent")
    judge.check("answer_mechanic_industry",
                contains_phrase(answer, "Health Care and Social Assistance"),
                "expected industry Health Care and Social Assistance")
    judge.check("answer_cicu_city", contains_phrase(answer, "Cincinnati"),
                "expected CICU city Cincinnati")
    judge.check("answer_cicu_ref_na",
                contains_phrase(answer, "NA") or contains_phrase(answer, "N/A"),
                "expected CICU reference code NA")
    judge.check("answer_cicu_education", contains_phrase(answer, "Master's degree"),
                "expected CICU education level Master's degree")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
