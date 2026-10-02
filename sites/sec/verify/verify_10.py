"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--10',
 'paths': ['/investor-alerts-bulletins/ponzi-schemes',
           '/investor-alerts-bulletins/cold-call',
           '/investor-alerts-bulletins/crypto'],
 'claims': [['warning sign 1', 'high returns with little or no risk'],
            ['warning sign 2', 'overly consistent returns'],
            ['cold flag 1', 'refuses to send'],
            ['cold flag 2', 'demands an immediate decision'],
            ['warning sign 3', 'unregistered investments with unlicensed sellers'],
            ['crypto return promise', 'guaranteed returns'],
            ['crypto payment', 'crypto assets, gift cards or wire transfers']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
