#!/usr/bin/env python3
"""Deterministic verifier for Medicare.gov--11."""
from review_contract import run_checks
from verify_lib import run_verifier

if __name__ == "__main__":
    run_verifier("Medicare.gov--11", run_checks)
