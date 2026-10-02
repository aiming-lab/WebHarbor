"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--7',
 'paths': ['/newsroom/press-releases/2026-98-',
           '/enforcement-litigation/litigation-releases\\?q=Meyer'],
 'claims': [['release number', '2026-98'],
            ['release date', 'sept\\.?\\s*30,?\\s*2026'],
            ['investments', 'spacex'],
            ['forfeited amount', '\\$?\\s*3,?000,?000'],
            ['litigation number', 'lr-?26659'],
            ['litigation respondents',
             'owen e\\.?\\s?h\\.?\\s*meyer and meyer global management llc']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
