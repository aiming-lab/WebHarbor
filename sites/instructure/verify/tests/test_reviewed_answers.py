"""Synthetic answer controls; these do not represent browser task completion."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reviewed import CONFIG, check_facts
from verify_lib import Judge
CASES = json.loads(Path(__file__).with_name('reviewed_answer_controls.json').read_text())

@pytest.mark.parametrize('case', CASES, ids=lambda c: c['task']+'-'+c['label'])
def test_scoped_facts(case):
    judge = Judge(case['task'], no_llm=True)
    check_facts(judge, case['answer'], CONFIG[case['task']]['facts'])
    assert judge.ok is case['expected'], judge.evidence
