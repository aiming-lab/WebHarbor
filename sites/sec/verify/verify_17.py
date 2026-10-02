"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--17',
 'paths': ['/edgar/company/0000886982',
           '/edgar/company/0000886982\\?type=10-K',
           '/edgar/filing/0000886982/0000886982-26-000091',
           '/edgar/company/0000886982\\?type=10-Q',
           '/edgar/company/0000789019',
           '/edgar/company/0000789019\\?type=10-K',
           '/edgar/filing/0000789019/0001193125-26-323660',
           '/edgar/company/0000789019\\?type=10-Q'],
 'claims': [['GS CIK', '0000886982'],
            ['GS state', '\\bde\\b'],
            ['GS SIC', '6211'],
            ['GS 10-K count', 'goldman[\\s\\S]{0,430}\\b1\\s+10-?k\\b'],
            ['GS newest 10-K date', '2026-02-25'],
            ['GS 10-K period',
             'goldman[^.]{0,200}period of report 2025-12-31|2026-02-25[^.]{0,80}period of '
             'report 2025-12-31'],
            ['GS 10-Q count', 'goldman[\\s\\S]{0,430}\\b3\\s+10-?q\\b'],
            ['GS 10-Q newest', '2026-08-03'],
            ['MS CIK', '0000789019'],
            ['MS state', '\\bwa\\b'],
            ['MS SIC', '7372'],
            ['MS 10-K count', 'microsoft[\\s\\S]{0,430}\\b3\\s+10-?k\\b'],
            ['MS newest 10-K date', '2026-07-29'],
            ['MS 10-K period', '2026-07-29[^.]{0,80}period of report 2026-06-30'],
            ['MS 10-Q count', 'microsoft[\\s\\S]{0,430}\\b4\\s+10-?q\\b'],
            ['MS 10-Q newest', '2026-04-29'],
            ['comparison', 'microsoft has more 10-?k']],
 'forbidden': [['wrong comparison', 'goldman sachs has more|goldman.{0,120}more 10-?ks'],
               ['wrong GS 10-K count', 'goldman[\\s\\S]{0,430}\\b[2-9]\\s+10-?k\\b'],
               ['wrong MS 10-K count',
                'microsoft[\\s\\S]{0,430}\\b[124-9]\\s+10-?k\\b(?!\\d)']],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
