"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--8',
 'paths': ['/submit-filings/forms-index\\?q=10-K',
           '/submit-filings/forms-index\\?q=8-K',
           '/submit-filings/forms-index\\?q=1-A'],
 'claims': [['10-K description', 'annual report pursuant to section 13 or 15\\(d\\)'],
            ['10-K SEC number', 'sec1673'],
            ['10-K updated', 'feb\\.?\\s*2025'],
            ['8-K SEC number', 'sec873'],
            ['1-A SEC number', 'sec486'],
            ['1-A statute', 'securities act of 1933'],
            ['pdf served', 'served|true|download|form10-k\\.pdf']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
