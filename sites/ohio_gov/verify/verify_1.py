#!/usr/bin/env python3
"""Verify Ohio.gov--1.

Phone-search chain: find the Aaron Smith at the Environmental Protection
Agency (phone number), then search for all listings named exactly
"Aaron Smith" (count + which agency each works for) and report the phone
number of the one at the Lottery Commission.

Frozen ground truth (tracked data snapshot): the EPA Aaron Smith is
614-728-0049. The exact-name search returns 4 listings: Dept of Rehab &
Corrections (330-746-3777), Environmental Protection Agcy (614-728-0049),
Lottery Commission (216-774-0177), and one listing with no agency shown
(410-703-6439).
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_all,
                        contains_count, contains_phone, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--1"
PHONE_PATH = "/help-center/phone-search"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: an agency-scoped Smith search, then the exact-name
    # search (first name Aaron + last name Smith)
    judge.check("searched_phone_by_last_name_and_agency",
                navigated_with_query(traj, PHONE_PATH, "lastName", "smith")
                and navigated_with_query(traj, PHONE_PATH, "agency", "environmental"),
                "required: /help-center/phone-search?lastName=Smith&agency=Environmental+Protection")
    judge.check("searched_phone_for_exact_name",
                navigated_with_query(traj, PHONE_PATH, "firstName", "aaron")
                and navigated_with_query(traj, PHONE_PATH, "lastName", "smith"),
                "required: /help-center/phone-search?firstName=Aaron&lastName=Smith")
    # answer: EPA phone, exact-name count, per-listing agencies, lottery phone
    judge.check("answer_epa_aaron_smith_phone", contains_phone(answer, "614-728-0049"),
                "expected EPA Aaron Smith phone: 614-728-0049")
    judge.check("answer_exact_name_count", contains_count(answer, 4),
                "expected: 4 listings named exactly Aaron Smith")
    judge.check("answer_listing_agencies",
                contains_all(answer, ["rehab", "lottery"]),
                "expected agencies include: Dept of Rehab & Corrections and the "
                "Lottery Commission (plus Environmental Protection; one listing "
                "shows no agency)")
    judge.check("answer_lottery_aaron_smith_phone", contains_phone(answer, "216-774-0177"),
                "expected Lottery Commission Aaron Smith phone: 216-774-0177")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
