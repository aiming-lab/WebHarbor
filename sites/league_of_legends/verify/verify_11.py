from verify_lib import run_verifier
from reviewed import run_checks

TASK_ID = 'League of Legends--11'

if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
