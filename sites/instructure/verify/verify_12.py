from verify_lib import run_verifier
from reviewed import run_checks

TASK_ID = 'Instructure--12'

if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
