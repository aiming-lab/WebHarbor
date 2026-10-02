"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--15',
 'paths': ['/login', '/account', '/edgar/company/0001318605', '/edgar/company/0001045810'],
 'claims': [['final count', '\\b3\\s+compan'],
            ['company 1', 'alphabet inc\\.?'],
            ['company 2', 'tesla,?\\s*inc\\.?'],
            ['company 3', 'nvidia corp'],
            ['ticker 1', '\\bgoogl\\b'],
            ['ticker 2', '\\btsla\\b'],
            ['ticker 3', '\\bnvda\\b']],
 'forbidden': [['Meta still listed', 'meta platforms']],
 'state': {'watchlist_items': {'added': [{'user_id': 4,
                                          'cik': '0001318605',
                                          'added_at': '2026-09-30'},
                                         {'user_id': 4,
                                          'cik': '0001045810',
                                          'added_at': '2026-09-30'}],
                               'removed': [{'user_id': 4, 'cik': '0001326801'}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
