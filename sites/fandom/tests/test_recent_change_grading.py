"""Ordinary wording for a zero-byte edit does not require unrequested totals."""
import importlib.util,json
from pathlib import Path
import pytest
SITE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fandom_grader',SITE/'verify/verify.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
C=json.loads((SITE/'verify/contract.json').read_text())['Fandom--6']
@pytest.mark.parametrize('ending',['Change: 0 bytes.','The byte change is 0.','No byte change.'])
def test_zero_change(ending):
 answer='200 revision rows.\nMon Mothma\nStarkFan42 — Reverted vandalism. '+ending
 g.check_claims(' '.join(answer.splitlines()),C['claims'])

def test_wrong_change():
 with pytest.raises(ValueError):
  g.check_claims('200 revision rows. Mon Mothma, StarkFan42, Reverted vandalism. Change: 20 bytes.',C['claims'])
