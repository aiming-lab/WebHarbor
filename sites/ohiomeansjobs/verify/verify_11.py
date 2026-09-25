"""Verify the current OhioMeansJobs--11 task."""
from refined_checks import run_checks
from verify_lib import run_verifier

if __name__ == "__main__":
    run_verifier("OhioMeansJobs--11", run_checks)
