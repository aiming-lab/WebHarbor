"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--0',
 'paths': ['/edgar/company/0000320193\\?type=10-K',
           '/edgar/filing/0000320193/0000320193-25-000079',
           '/edgar/company/0000320193\\?type=10-Q',
           '/edgar/filing/0000320193/0000320193-26-000020'],
 'claims': [['10-K filing date', '10-?k[^;]{0,200}2025-10-31|2025-10-31[^;]{0,80}10-?k'],
            ['10-K period', '2025-09-27'],
            ['10-K accession', '0000320193-25-000079'],
            ['10-Q filing date', '10-?q[^;]{0,200}2026-07-31|2026-07-31[^;]{0,80}10-?q'],
            ['10-Q period', '2026-06-27'],
            ['10-Q accession', '0000320193-26-000020'],
            ['10-K covers the longer period',
             '10-?k(?:(?!10-?q)[^;]){0,24}longer|longer(?:(?!10-?q)[^;]){0,24}10-?k']],
 'forbidden': [['reversed comparison direction',
                '10-?q[^;]{0,12}longer|longer[^;]{0,15}10-?q']],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
