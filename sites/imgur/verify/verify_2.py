#!/usr/bin/env python3
"""Reviewed Imgur task 2."""
from reviewed import run_checks
from verify_lib import run_verifier
TASK_ID = "Imgur--2"
if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
