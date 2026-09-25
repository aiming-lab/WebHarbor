#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--14"
ASSISTANT_PATH = "/help-center/ohio-assistant"
DRIVER_LICENSES = "/residents/resources/driver-licenses"
DRIVER_TRAINING = "/residents/resources/driver-training"
DIRECTORY_PATH = "/help-center/state-directory"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the assistant with the driver-license question, the
    # Driver Licenses + Driver Training resources, and the State Directory
    # searched for the BMV
    judge.check("asked_assistant_driver_license",
                navigated_with_query(traj, ASSISTANT_PATH, "q", "driver license"),
                "required: /help-center/ohio-assistant?q=...driver license...")
    check_visited_path(judge, traj, "visited_driver_licenses", DRIVER_LICENSES)
    judge.check("searched_directory_for_bmv",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "motor vehicles"),
                "required: /help-center/state-directory?q=Bureau of Motor Vehicles")
    # answer: assistant titles, also-serves-as + Real ID, training office,
    # BMV contact method
    judge.check("answer_state_issued_id",
                contains_phrase(answer, "state-issued identification")
                or contains_phrase(answer, "form of state-issued id"),
                "expected: an Ohio driver license is also a form of state-issued identification")
    judge.check("answer_real_id",
                contains_phrase(answer, "real id"),
                "expected: with proper documents the license can serve as a federally "
                "compliant Real ID for air travel and access to federal facilities")
    judge.check("answer_bmv_contact", contains_phrase(answer, "contact list and chat"),
                "expected BMV contact method: contact list and chat")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
