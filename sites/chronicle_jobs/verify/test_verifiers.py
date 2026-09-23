"""Regrade saved browser packages and adversarial copies without resetting a live site.

Set WH_REVIEW_RUNS to the parent directory containing Chronicle Jobs--0, etc.
The source evidence is read-only; every control writes only into pytest's tmp_path.
Without that artifact, pure contract tests remain available in test_coherent_tasks.py
and test_review_regressions.py. Recorded evidence is not claimed as a new browser run.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize('number', range(30))
@pytest.mark.parametrize('control', ['honest', 'empty_answer', 'wrong_origin', 'wrong_identity', 'missing_shot', 'stale_wording'])
def test_saved_browser_contract(number, control, tmp_path):
    root = os.environ.get('WH_REVIEW_RUNS')
    if not root:
        pytest.skip('Set WH_REVIEW_RUNS to saved browser evidence; no live preview is reset')
    source = Path(root) / f'Chronicle Jobs--{number}'
    trajectory = json.loads((source / 'trajectory.json').read_text())
    for name in ['screenshots', 'initial.db', 'after.db']:
        (tmp_path / name).symlink_to(source / name)
    if control == 'empty_answer':
        trajectory['final_answer'] = ''
    elif control == 'wrong_origin':
        for step in trajectory['steps']:
            for key in ['url', 'url_before', 'url_after']:
                if step.get(key):
                    step[key] = step[key].replace('localhost:', 'other-site.invalid:')
    elif control == 'wrong_identity':
        trajectory['task_id'] = 'Unrelated task--0'
    elif control == 'missing_shot':
        for step in trajectory['steps']:
            step['screenshot_before'] = step['screenshot_after'] = 'missing.png'
    elif control == 'stale_wording':
        # Unchanged tasks retain their existing identity gates; revised tasks also
        # reject evidence captured for an earlier wording with the same task ID.
        specs = json.loads((HERE / 'coherent_tasks.json').read_text())
        if str(number) not in specs:
            return
        trajectory['task'] = 'Superseded concatenated task'
    (tmp_path / 'trajectory.json').write_text(json.dumps(trajectory))
    proc = subprocess.run([sys.executable, str(HERE / f'verify_{number}.py'),
                           '--run_dir', str(tmp_path)], capture_output=True, text=True)
    verdict = json.loads(proc.stdout)
    assert verdict['pass'] == (control == 'honest'), verdict
    assert proc.returncode == (0 if control == 'honest' else 1)
