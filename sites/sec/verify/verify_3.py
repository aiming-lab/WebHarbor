"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--3',
 'paths': ['/edgar/company/0001318605\\?type=8-K',
           '/edgar/filing/0001318605/0001628280-26-063820',
           '/edgar/filing/0001318605/0001628280-26-063820/document',
           '/edgar/filing/0001318605/0001628280-26-049213'],
 'claims': [['first 8-K date', '2026-09-29'],
            ['first 8-K items', '1\\.01[\\s,]*1\\.02[\\s,]*2\\.03[\\s,]*(and[\\s,]+)?9\\.01'],
            ['first 8-K accession', '0001628280-26-063820'],
            ['first 8-K period',
             '8-?k[^;]{0,200}period(?: of report)?(?: is|:)?\\s+2026-09-29'],
            ['second 8-K date', '2026-07-22'],
            ['second 8-K items', '2\\.02[\\s,]*(and[\\s,]+)?9\\.01'],
            ['second 8-K accession', '0001628280-26-049213'],
            ['second 8-K period', 'period(?: of report)?(?: is|:)?\\s+2026-07-22'],
            ['shared items', '9\\.01'],
            ['primary document filename', 'tsla-20260929\\.htm']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
