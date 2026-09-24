#!/usr/bin/env python3
"""Verify Ohio.gov--11.

Help Center FAQ chain, three categories: Government Questions (what the
Bureau of Vital Statistics can provide, which commission helps residents
search Ohio's laws, how many questions the category lists), New Resident
Questions (how many questions it lists, how long new residents have to
transfer an out-of-state driver license and vehicle registration, where the
answer says they can register to vote), and Driving Questions (which
department helps you find your local BMV office).

Frozen ground truth (tracked data snapshot): the Government Questions
category holds 16 FAQs; the birth-certificate answer says the Ohio Department
of Health's Bureau of Vital Statistics can provide copies of birth
certificates and similar documents (e.g., death certificates, adoption
records); the search-Ohio's-laws answer names the Ohio Legislative Service
Commission. The New Resident Questions category holds 6 FAQs; the transfer
answer says within 30 days of establishing residency; the vote answer says
Ohio's Online Voter Registration System. The Driving Questions BMV answer
names the Ohio Department of Public Safety.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Ohio.gov--11"
GOV_FAQ = "/help-center/faqs/government"
NEW_RESIDENT_FAQ = "/help-center/faqs/new-residents"
DRIVING_FAQ = "/help-center/faqs/driving-and-transportation"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: all three FAQ category pages
    check_visited_path(judge, traj, "visited_government_faq", GOV_FAQ)
    check_visited_path(judge, traj, "visited_new_resident_faq", NEW_RESIDENT_FAQ)
    check_visited_path(judge, traj, "visited_driving_faq", DRIVING_FAQ)
    # answer: Government Questions facts
    judge.check("answer_vital_statistics",
                contains_phrase(answer, "bureau of vital statistics"),
                "expected: the Bureau of Vital Statistics provides copies of birth certificates")
    judge.check("answer_birth_certificates",
                contains_phrase(answer, "birth certificate"),
                "expected: copies of birth certificates and similar documents")
    judge.check("answer_law_search_commission",
                contains_phrase(answer, "legislative service commission"),
                "expected: the Ohio Legislative Service Commission helps residents search Ohio's laws")
    judge.check("answer_gov_question_count", contains_count(answer, 16),
                "expected: 16 questions in the Government Questions category")
    # answer: New Resident Questions facts
    judge.check("answer_new_resident_question_count", contains_count(answer, 6),
                "expected: 6 questions in the New Resident Questions category")
    judge.check("answer_transfer_deadline",
                contains_phrase(answer, "30 days"),
                "expected: transfer within 30 days of establishing residency")
    judge.check("answer_voter_registration",
                contains_phrase(answer, "online voter registration"),
                "expected: register to vote via Ohio's Online Voter Registration System")
    # answer: Driving Questions fact
    judge.check("answer_bmv_department",
                contains_phrase(answer, "department of public safety"),
                "expected: the Ohio Department of Public Safety helps you find your local BMV office")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
