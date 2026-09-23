#!/usr/bin/env python3
"""Reviewed Google Shopping task 1."""
from reviewed import run_checks
from verify_lib import run_verifier
TASK_ID = "Google Shopping--1"
if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
