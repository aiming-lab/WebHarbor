"""Verify the current Ohio.gov--2 task."""
from refined_checks import run_checks
from verify_lib import run_verifier

if __name__ == "__main__":
    run_verifier("Ohio.gov--2", run_checks)
