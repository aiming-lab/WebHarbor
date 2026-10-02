"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--14',
 'paths': ['/login',
           '/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization',
           '/submit-tip-or-complaint/question-confirmation/Q-',
           '/resources-investors/investor-alerts-bulletins/cold-call',
           '/subscribe'],
 'claims': [['question reference', 'q-[a-z0-9]{8}'],
            ['red flag',
             'refuses to send written information|demands an immediate decision|promises '
             "guaranteed returns|'confidential'"],
            ['subscription', 'now subscribed|subscribed']],
 'forbidden': [['fake reference', 'q-0{8}|q-12345678']],
 'state': {'questions': {'added': [{'name': 'Carol Davis',
                                    'email': 'carol.d@test.com',
                                    'topic': 'investment professional',
                                    'submitted_at': '2026-09-30',
                                    'reference': {'regex': 'Q-[A-Z0-9]{8}'},
                                    'question': {'min_len': 20,
                                                 'patterns': ['register|licen[cs]',
                                                              'check|find|verif|confirm|know']}}]},
           'email_subscriptions': {'added': [{'email': 'updates.carol@example.com',
                                              'topics': 'investor alerts',
                                              'submitted_at': '2026-09-30'}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
