"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--4',
 'paths': ['/enforcement-litigation/litigation-releases\\?q=Noble',
           '/enforcement-litigation/litigation-releases/lr-26660',
           '/enforcement-litigation/administrative-proceedings\\?q=Brown'],
 'claims': [['Brown/Grant/Noble number', 'lr-?26660'],
            ['Noble total', '1,?074,?984\\.36'],
            ['Brown admin release', '34-106553'],
            ['Brown admin file number', '3-22766']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
