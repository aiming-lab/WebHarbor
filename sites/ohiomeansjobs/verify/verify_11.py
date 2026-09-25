#!/usr/bin/env python3
"""Verify OhioMeansJobs--11.

Without logging in, use the Help Center to answer: the exact password
requirements, which email address the password reset email comes from, which
help section contains the FAQ about finding scholarship information, what the
site says it aggregates over 1 million of, about how long the career profile
quiz takes (per the job seeker help section), and the first FAQ topic covered
in the employer help section.

Frozen ground truth (seed DB): password requirements = 8 to 20 characters
long, at least one number, one symbol (excluding ' @ - "), a combination of
upper and lower case characters; the reset email comes from
omjnoreply@monster.com; the scholarship FAQ appears in the 'Common Questions'
section (and also in 'Help for Students and Education'); the site aggregates
over 1 million available scholarships; the career profile quiz takes about
30 minutes (job seeker help); the employer help section's first FAQ topic is
'Steps to register for an Employer account'. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer,
                        run_verifier)

TASK_ID = "OhioMeansJobs--11"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_help_center", "/help-center")
    check_visited_path(judge, traj, "visited_common_questions", "/help-center/common-questions")
    check_visited_path(judge, traj, "visited_education_section", "/help-center/education")
    check_visited_path(judge, traj, "visited_job_seeker_section", "/help-center/job-seeker")
    check_visited_path(judge, traj, "visited_employer_help", "/help-center/employers")
    # answer facts
    judge.check("answer_pw_length",
                contains_phrase(answer, "8 to 20") or contains_phrase(answer, "8-20"),
                "expected 8 to 20 characters long")
    judge.check("answer_pw_number", contains_phrase(answer, "number"),
                "expected at least one number")
    judge.check("answer_pw_symbol", contains_phrase(answer, "symbol"),
                "expected one symbol")
    judge.check("answer_pw_case",
                contains_phrase(answer, "upper") and contains_phrase(answer, "lower"),
                "expected upper and lower case characters")
    judge.check("answer_reset_email", contains_phrase(answer, "omjnoreply@monster.com"),
                "expected omjnoreply@monster.com")
    judge.check("answer_scholarship_section",
                contains_phrase(answer, "Common Questions"),
                "expected the scholarship FAQ in the Common Questions section "
                "(also listed under Help for Students and Education)")
    judge.check("answer_million_scholarships",
                contains_phrase(answer, "scholarship") and contains_phrase(answer, "1 million"),
                "expected 'aggregates over 1 million available scholarships'")
    judge.check("answer_quiz_duration",
                contains_phrase(answer, "30 minutes") or contains_phrase(answer, "about 30"),
                "expected the career profile quiz to take about 30 minutes")
    judge.check("answer_employer_first_faq",
                contains_phrase(answer, "Steps to register for an Employer account"),
                "expected the employer help first FAQ topic "
                "'Steps to register for an Employer account'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
