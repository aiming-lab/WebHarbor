#!/usr/bin/env python3
"""Verify OhioMeansJobs--15.

Explore the employer side: report the four statistics shown on the For
Employers page (employers on board, active job postings, resumes available,
companies hiring); find the page listing hiring resources for employers and
report its name and the first three resources listed there; follow the Hire
a Veteran resource and report how many job results it shows; finally report
the first FAQ topic covered in the employer help section.

Frozen ground truth (seed DB): For Employers page stats — 6,492 employers on
board, 160 active job postings, 1,460,686 resumes available, 104 companies
hiring; the resources page is 'Resources For Employers'
(/for-employers/resources-for-employers); its first three resources are 'Hire
a Veteran', 'Hiring People with Disabilities', 'Hiring Restored Citizens';
the Hire a Veteran resource links to /jobs/search?tjt=veteran which shows 60
job results; the employer help section's first FAQ topic is 'Steps to
register for an Employer account'. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, navigated_jobs_search, run_verifier)

TASK_ID = "OhioMeansJobs--15"
EMPLOYERS_ON_BOARD = 6492
ACTIVE_POSTINGS = 160
RESUMES_AVAILABLE = 1460686
COMPANIES_HIRING = 104
VETERAN_RESULTS = 60
FIRST_THREE = ("Hire a Veteran", "Hiring People with Disabilities",
               "Hiring Restored Citizens")
FIRST_FAQ = "Steps to register for an Employer account"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_for_employers", "/for-employers")
    check_visited_path(judge, traj, "visited_resources_for_employers",
                       "/for-employers/resources-for-employers")
    check_visited_path(judge, traj, "visited_employer_help", "/help-center/employers")
    # answer facts
    judge.check("answer_employers_on_board", contains_count(answer, EMPLOYERS_ON_BOARD),
                f"expected {EMPLOYERS_ON_BOARD:,} employers on board")
    judge.check("answer_active_postings", contains_count(answer, ACTIVE_POSTINGS),
                f"expected {ACTIVE_POSTINGS} active job postings")
    judge.check("answer_resumes_available", contains_count(answer, RESUMES_AVAILABLE),
                f"expected {RESUMES_AVAILABLE:,} resumes available")
    judge.check("answer_companies_hiring", contains_count(answer, COMPANIES_HIRING),
                f"expected {COMPANIES_HIRING} companies hiring")
    judge.check("answer_resources_page_name",
                contains_phrase(answer, "Resources for Employers")
                or contains_phrase(answer, "Resources For Employers"),
                "expected the page name 'Resources For Employers'")
    for res in FIRST_THREE:
        judge.check(f"answer_resource_{res[:24]}", contains_phrase(answer, res),
                    f"expected resource '{res}'")
    judge.check("visited_hire_a_veteran_search",
                navigated_jobs_search(traj, tjt=["veteran"]),
                "required: /jobs/search with tjt=veteran (the Hire a Veteran resource)")
    judge.check("answer_veteran_job_results", contains_count(answer, VETERAN_RESULTS),
                f"expected {VETERAN_RESULTS} job results for the Hire a Veteran resource")
    judge.check("answer_first_faq_topic", contains_phrase(answer, FIRST_FAQ),
                f"expected the first FAQ topic '{FIRST_FAQ}'")
    from verify_lib import db_query
    old = {r['id'] for r in db_query(initial_db, 'SELECT id FROM contact_messages')}
    rows = [r for r in db_query(after_db, 'SELECT * FROM contact_messages') if r['id'] not in old]
    judge.check('onboarding_inquiry', len(rows) == 1 and rows[0]['name'] == 'Taylor Reed' and rows[0]['email'] == 'taylor.reed@example.com' and rows[0]['subject'] == 'Veteran hiring support', 'requested sender and subject')
    if rows:
        judge.check('company_hiring_goal', all(x in rows[0]['message'].lower() for x in ['lakefront manufacturing', 'veteran', 'onboarding']), 'company and recruiting goal')
    judge.check('submission_confirmed', contains_phrase(answer, 'sent') or contains_phrase(answer, 'submitted'), 'inquiry confirmation')


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
