#!/usr/bin/env python3
"""Verify OhioMeansJobs--6.

Take the Career Profile Quiz answering as someone who enjoys leading projects,
competing and persuading, but dislikes tools/machines and organizing detailed
records. Report the top trait with its score and the first two suggested
careers, then search the board for the first suggested career and report the
title and employer of the newest matching job.

Frozen ground truth (seed DB + site logic): the profile is Enterprising with
score 2 (both Enterprising questions answered "Definitely like me"); the first
two suggested careers are 'Project Manager' and 'Sales Account Executive'.
The default date-sorted "Project Manager" search returns 'Manager, Sales
Incentive Compensation Operations' @ Vertiv Corporation (posted 2026-09-24)
as the newest match. Stateful task: allowed delta = career_quiz_results +1
(top_trait Enterprising); nothing else.
"""
from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        db_query, final_answer, navigated_jobs_search,
                        run_verifier)

TASK_ID = "OhioMeansJobs--6"
STATEFUL_TABLES = ("career_quiz_results",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_quiz_intro", "/job-seekers/find-a-job/career-profile-quiz")
    check_visited_path(judge, traj, "visited_quiz_form", "/career-quiz/start")
    judge.check("visited_pm_search",
                navigated_jobs_search(traj, tjt=["Project Manager", "project+manager", "project%20manager"]),
                "required: /jobs/search with tjt=Project Manager")
    # answer facts
    judge.check("answer_top_trait", contains_phrase(answer, "Enterprising"),
                "expected top trait Enterprising")
    judge.check("answer_trait_score", contains_count(answer, 2),
                "expected Enterprising score 2 (of 2)")
    judge.check("answer_career_pm", contains_phrase(answer, "Project Manager"),
                "expected first suggested career 'Project Manager'")
    judge.check("answer_career_sales", contains_phrase(answer, "Sales Account Executive"),
                "expected second suggested career 'Sales Account Executive'")
    judge.check("answer_newest_title",
                contains_phrase(answer, "Manager, Sales Incentive Compensation Operations"),
                "expected newest PM match 'Manager, Sales Incentive Compensation Operations'")
    judge.check("answer_newest_employer", contains_phrase(answer, "Vertiv"),
                "expected employer Vertiv Corporation")
    # DB after-state: exactly one quiz result, Enterprising
    results = db_query(after_db, "SELECT * FROM career_quiz_results")
    seed_results = db_query(initial_db, "SELECT * FROM career_quiz_results")
    judge.check("one_quiz_result_added",
                len(results) == len(seed_results) + 1,
                f"quiz_results before={len(seed_results)} after={len(results)}")
    if results:
        latest = results[-1]
        judge.check("quiz_top_trait_enterprising", latest["top_trait"] == "Enterprising",
                   f"top_trait={latest['top_trait']!r}")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
