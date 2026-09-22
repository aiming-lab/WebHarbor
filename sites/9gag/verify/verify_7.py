#!/usr/bin/env python3
"""Verify the multi-source investigation in 9GAG--7."""

from research_checks import run_checks_for
from verify_lib import run_verifier

TASK_ID = "9GAG--7"


def run_checks(judge, traj, initial_db, after_db):
    run_checks_for(7, judge, traj, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
