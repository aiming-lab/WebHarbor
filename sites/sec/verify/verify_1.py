"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--1',
 'paths': ['/edgar/full-text-search\\?q=artificial\\+intelligence&forms=10-K',
           '/edgar/full-text-search\\?q=artificial\\+intelligence&forms=8-K',
           '/edgar/full-text-search\\?q=artificial\\+intelligence&forms=10-K&datea=2020-01-01'],
 'claims': [['10-K total', '10-?k[^.]{0,80}10000|10000[^.]{0,80}10-?k'],
            ['top result company', 'artificial intelligence technology solutions'],
            ['top result filing date', '0001161697-21-000289|2021-06-01'],
            ['8-K total', '8-?k[^.]{0,80}10000|10000[^.]{0,80}8-?k'],
            ['narrowed count', '(2020-01-01|narrowed)[^.]{0,80}\\b7\\s+documents?\\b']],
 'forbidden': [['wrong narrowed count',
                '(2020-01-01|narrowed)[^.]{0,80}\\b(6|8|9|1\\d)\\s+documents?\\b']],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
