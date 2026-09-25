#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
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
    check_visited_path(judge, traj, "visited_new_resident_faq", NEW_RESIDENT_FAQ)
    check_visited_path(judge, traj, "visited_driving_faq", DRIVING_FAQ)
    # answer: Government Questions facts
    # answer: New Resident Questions facts
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
