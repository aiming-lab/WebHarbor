#!/usr/bin/env python3
"""Verify Ohio.gov--0.

Acupuncturist license chain: find the acupuncturists entry in the Licenses &
Permits directory (issuing agency, agency website, contact method), then look
the agency up in the State Directory (how many social media links its entry
shows), then filter the licenses directory by that agency and report how many
licenses it issues in total.

Frozen ground truth (tracked data snapshot): the Acupuncturists row is issued
by the Medical Board with agency website https://med.ohio.gov/ and contact
method "contact list and form". The Medical Board's State Directory entry
carries 4 social links (X / Facebook / YouTube / LinkedIn). The licenses
directory filtered by agency "Medical Board" shows 12 licenses.
"""
from verify_lib import (check_only_tables_changed, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--0"
LICENSES_PATH = "/jobs/resources/licenses-and-permits"
DIRECTORY_PATH = "/help-center/state-directory"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the licenses directory filtered for acupuncturists,
    # the State Directory searched for the issuing agency, and the licenses
    # directory filtered by that agency
    judge.check("visited_licenses_directory",
                navigated_with_query(traj, LICENSES_PATH, "q", "acupunctur"),
                "required: /jobs/resources/licenses-and-permits?q=acupunctur...")
    judge.check("visited_state_directory_for_medical_board",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "medical board"),
                "required: /help-center/state-directory?q=Medical+Board")
    judge.check("filtered_licenses_by_medical_board",
                navigated_with_query(traj, LICENSES_PATH, "agency", "medical board"),
                "required: /jobs/resources/licenses-and-permits?agency=Medical+Board")
    # answer: issuing agency, agency website, contact method, social count,
    # total licenses issued by the agency
    judge.check("answer_issuing_agency", contains_phrase(answer, "Medical Board"),
                "expected: Medical Board")
    judge.check("answer_agency_website", contains_phrase(answer, "med.ohio.gov"),
                "expected: med.ohio.gov")
    judge.check("answer_contact_method", contains_phrase(answer, "contact list and form"),
                "expected: contact list and form")
    judge.check("answer_social_links_count", bool(__import__('re').search(r'(?:4|four)\s+social', answer, __import__('re').I)),
                "expected: 4 social media links")
    judge.check("answer_medical_board_license_total", bool(__import__('re').search(r'(?:12|twelve)\s+(?:different\s+)?licenses', answer, __import__('re').I)),
                "expected: 12 licenses issued by the Medical Board in total")
    check_read_only(judge, initial_db, after_db)

    judge.check('all_social_channels', all(contains_phrase(answer, x) for x in ['Facebook', 'YouTube', 'LinkedIn']) and __import__('re').search(r'\b(?:X|Twitter)\b', answer, __import__('re').I), 'X, Facebook, YouTube, LinkedIn')

if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
