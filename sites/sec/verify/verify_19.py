"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--19',
 'paths': ['litigation-releases\\?q=&year=2026',
           '/enforcement-litigation/litigation-releases/lr-26661',
           '/enforcement-litigation/administrative-proceedings\\?q=OTC\\+Link',
           '/enforcement-litigation/administrative-proceedings/34-106458-s',
           '/newsroom/whats-new',
           '/enforcement-litigation/litigation-releases/lr-26662'],
 'claims': [['year count', '\\b100\\s+releases?\\b'],
            ['Bernardi number', 'lr-?26661'],
            ['Bernardi date', 'sept\\.?\\s*30,?\\s*2026|september\\s*30,?\\s*2026'],
            ['Bernardi company', 'gigamedia access corporation'],
            ['OTC title',
             'sec censures otc link llc for repeated compliance failures related to '
             'regulation sci'],
            ['whats-new number', 'lr-?26662'],
            ['whats-new division', 'enforcement']],
 'forbidden': [['wrong year count', '\\b(99|101)\\s+releases?\\b']],
 'state': {}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
