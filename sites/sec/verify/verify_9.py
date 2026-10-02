"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--9',
 'paths': ['/fast-answers/form10k', '/fast-answers/form10q', '/fast-answers/proxy'],
 'claims': [['annual report', '10-?k.{0,180}annual report'],
            ['annual statements', 'audited financial'],
            ['annual deadline', '60 (?:to|-) 90 days'],
            ['quarterly statements', 'unaudited financial'],
            ['quarterly deadline', '40 (?:to|-) 45 days'],
            ['proxy purpose', 'proxy.{0,500}(?:vote|voting|shareholder|meeting)']],
 'forbidden': [],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
