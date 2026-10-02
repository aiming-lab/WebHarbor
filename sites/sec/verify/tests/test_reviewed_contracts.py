from pathlib import Path
import json
import sys
import pytest

V = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V))
from contract_engine import check_claims  # noqa: E402

SPECS = json.loads((V / 'contract.json').read_text())
CASES = json.loads((V / 'tests' / 'answer_controls.json').read_text())


@pytest.mark.parametrize('case', CASES,
                         ids=[c['task'] + ' ' + c['name'] for c in CASES])
def test_declared_answer_polarity(case):
    if case['expected']:
        check_claims(case['answer'], SPECS[case['task']]['claims'])
    else:
        with pytest.raises(ValueError):
            check_claims(case['answer'], SPECS[case['task']]['claims'])


def test_contract_covers_every_task():
    tasks = [json.loads(line)['id'] for line
             in (V.parent / 'tasks.jsonl').read_text().splitlines() if line.strip()]
    assert sorted(SPECS) == sorted(tasks)


def test_contract_task_text_matches_tasks_file():
    tasks = {json.loads(line)['id']: json.loads(line)['ques'] for line
             in (V.parent / 'tasks.jsonl').read_text().splitlines() if line.strip()}
    for tid, spec in SPECS.items():
        assert spec['task'] == tasks[tid], tid


def test_real_signup_password_with_fresh_salts():
    import bcrypt
    password = 'ReviewPassword42!'
    for _ in range(2):
        value = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
        assert check_password_shape(value, password)
        assert not check_password_shape(value, 'different-password')


def check_password_shape(value, password):
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), str(value).encode())
    except (ValueError, TypeError):
        return False
