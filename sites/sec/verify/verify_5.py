"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--5',
 'paths': ['/enforcement-litigation/administrative-proceedings\\?q=Black',
           '/enforcement-litigation/administrative-proceedings/34-106538-s',
           '/login',
           '/submit-tip-or-complaint/tcr-disclaimer',
           '/submit-tip-or-complaint/report-possible-securities-law-violations',
           '/submit-tip-or-complaint/confirmation/TCR-'],
 'claims': [['order date', 'sept\\.?\\s*30,?\\s*2026'],
            ['file number count', '\\b7\\s+file numbers?\\b|3-22759|3-22765'],
            ['Black penalty', '\\$?\\s*125,?000'],
            ['MacKechnie penalty', '\\$?\\s*85,?000'],
            ['resource count', '\\b7\\s+(order\\s+)?pdfs?\\b|\\b7\\s+resources?\\b'],
            ['first resource label', 'order\\s*-?\\s*quillan black'],
            ['TCR reference', 'tcr-[a-z0-9]{8}']],
 'forbidden': [['wrong Black penalty',
                "\\$?\\s*85,?000\\s*(for|to)\\s+(quillan\\s+)?black|black(?:'s)?\\s+(was\\s+)?(fined|ordered|penalized|penalty)[^.]{0,25}\\$?\\s*85,?000"],
               ['wrong MacKechnie penalty',
                "\\$?\\s*125,?000\\s*(for|to)\\s+(tyler\\s+)?mackechnie|mackechnie(?:'s)?\\s+(was\\s+)?(fined|ordered|penalized|penalty)[^.]{0,25}\\$?\\s*125,?000"]],
 'state': {'tips': {'added': [{'user_id': 2,
                               'name': 'Bob Chen',
                               'email': 'bob.c@test.com',
                               'violation_type': 'broker misconduct',
                               'subject_firm': None,
                               'submitted_at': '2026-09-30',
                               'reference': {'regex': 'TCR-[A-Z0-9]{8}'},
                               'details': {'min_len': 20,
                                           'patterns': ['unregistered|unlicensed',
                                                        'broker|swap']}}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
