#!/usr/bin/env python3
"""Reviewed Imgur task 22."""
from reviewed import run_checks
from verify_lib import run_verifier
TASK_ID = "Imgur--22"
if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
