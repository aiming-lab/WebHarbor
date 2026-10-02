"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--18',
 'paths': ['/resources-investors/investor-alerts-bulletins/crypto-asset',
           '/fast-answers/ponzi',
           '/submit-tip-or-complaint/tcr-disclaimer',
           '/submit-tip-or-complaint/report-possible-securities-law-violations',
           '/submit-tip-or-complaint/confirmation/TCR-'],
 'claims': [['red flag 1', 'guaranteed returns|celebrity endorsements|exclusive access'],
            ['red flag 2',
             'crypto assets,?\\s*gift cards or wire transfers|recruits?\\s+you to bring in '
             'friends'],
            ['Ponzi promise', 'high returns with little or no risk'],
            ['TCR reference', 'tcr-[a-z0-9]{8}']],
 'forbidden': [],
 'state': {'tips': {'added': [{'user_id': None,
                               'name': 'Jordan Lee',
                               'email': 'jordan.lee@test.com',
                               'violation_type': 'fraud',
                               'subject_firm': None,
                               'submitted_at': '2026-09-30',
                               'reference': {'regex': 'TCR-[A-Z0-9]{8}'},
                               'details': {'min_len': 20,
                                           'patterns': ['crypto|token',
                                                        'doubl|guarantee']}}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
