"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--11',
 'paths': ['/rules-regulations/rulemaking-activity',
           '/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization',
           '/submit-tip-or-complaint/question-confirmation/Q-'],
 'claims': [['Interval Fund Modernization; Expansion of Multiple Share Class to Registered '
             'Closed-End Management Investment Companies and Business Development Companies '
             'file',
             's7\\-2026\\-34'],
            ['Interval Fund Modernization; Expansion of Multiple Share Class to Registered '
             'Closed-End Management Investment Companies and Business Development Companies '
             'date',
             'sept\\.\\ 30,\\ 2026'],
            ['S7-2026-34 release 33-11444', '33\\-11444'],
            ['S7-2026-34 release 34-106534', '34\\-106534'],
            ['S7-2026-34 release IC-36351', 'ic\\-36351'],
            ['proposal status', 'proposed'],
            ['question reference', 'q-[a-z0-9]{8}']],
 'forbidden': [],
 'state': {'questions': {'added': [{'name': 'Evan Park',
                                    'email': 'evan.park@example.com',
                                    'topic': 'other',
                                    'submitted_at': '2026-09-30',
                                    'reference': {'regex': 'Q-[A-Z0-9]{8}'},
                                    'question': {'regex': '(?s)(?=.*(?:S7-2026-34|[Ii]nterval))(?=.*(?:effect|force|apply|applies|change|redemption)).{20,}'}}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
