"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--13',
 'paths': ['/login',
           '/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional',
           '/submit-tip-or-complaint/complaint-confirmation/IC-',
           '/account'],
 'claims': [['complaint reference', 'ic-[a-z0-9]{8}'],
            ['account firm', 'granite harbor capital llc']],
 'forbidden': [['fake reference', 'ic-0{8}|ic-12345678']],
 'state': {'complaints': {'added': [{'user_id': 1,
                                     'name': 'Alice Johnson',
                                     'email': 'alice.j@test.com',
                                     'your_role': 'individual investor',
                                     'issue_type': 'unauthorized trading',
                                     'subject_firm': 'Granite Harbor Capital LLC',
                                     'subject_person': 'T. Brooks',
                                     'subject_ticker': 'GRHN',
                                     'submitted_at': '2026-09-30',
                                     'reference': {'regex': 'IC-[A-Z0-9]{8}'},
                                     'address': {'min_len': 5},
                                     'phone': {'min_len': 7},
                                     'details': {'min_len': 20,
                                                 'patterns': ['unauthori[sz]ed|without.{0,30}(?:authori|permission|consent)|never '
                                                              'approved']}}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
