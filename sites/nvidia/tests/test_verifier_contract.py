#!/usr/bin/env python3
"""Verifier CLI/input-contract regressions for the NVIDIA site verifiers.

These tests pin the contract that `agent_demo/eval_judge.py --verifier True` relies on:
the verifier must run with `--run_dir` alone (databases fetched from `--container` /
`$WH_CONTAINER`), must accept a production-recorder trajectory (`task`/`start_url`,
no `query`, no `task.json`, no `final_url`), must accept `--no_llm`, and must return a
structured INFRA verdict (exit 2) for malformed inputs instead of a traceback.

Run with docker available and a running NVIDIA container:
  WH_CONTAINER=wh107-nvidia-site python3 -B -m unittest discover -s sites/nvidia/tests

Screenshots in the fixtures are decoded copies of a shipped product PNG; these tests
verify the input contract, not visual fidelity. Evidence files are written outside the
source tree (TEST_OUT or a temporary directory).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / 'verify'
CONTAINER = os.environ.get('WH_CONTAINER', '')
PNG_SOURCE = SITE / 'static' / 'images' / 'products' / 'geforce-rtx-5090.png'
TASKS = {json.loads(line)['id']: json.loads(line)
         for line in (SITE / 'tasks.jsonl').read_text().splitlines() if line.strip()}


def production_shape_trajectory(task_id='NVIDIA--0', answer=None):
    row = TASKS[task_id]
    urls = ['http://127.0.0.1:21113/', 'http://127.0.0.1:21113/products/geforce-rtx-5090']
    steps = []
    for index, url in enumerate(urls):
        steps.append({
            'step': index, 'url': url, 'title': 'fixture', 'thought': 'fixture',
            'action': 'click', 'params': {},
            'screenshot_before': f'step_{index:03d}.png',
            'screenshot_after': f'step_{index + 1:03d}.png',
            'action_result': {'is_done': False, 'success': True, 'error': None, 'extracted_content': ''},
        })
    return {
        'task': row['ques'], 'task_id': task_id, 'start_url': urls[0], 'model': 'fixture',
        'max_steps': 30, 'steps': steps, 'terminated': True, 'termination_reason': 'agent_done',
        'final_answer': answer if answer is not None else 'The GeForce RTX 5090 has 32 GB of GDDR7 memory.',
        'judge_rubric': row['judge_rubric'], 'verifier_path': row['verifier_path'],
    }


def write_fixture(folder, trajectory, with_task_json=False, screenshots=3, tiny_png=False):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'trajectory.json').write_text(json.dumps(trajectory, indent=2) + '\n')
    if with_task_json:
        (folder / 'task.json').write_text(json.dumps(TASKS[trajectory['task_id']], indent=2) + '\n')
    if screenshots:
        shots = folder / 'screenshots'
        shots.mkdir(exist_ok=True)
        tiny = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00'
                b'\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
                b'\x00\x00\x00\x00IEND\xaeB`\x82')
        for index in range(screenshots):
            target = shots / f'step_{index:03d}.png'
            if tiny_png:
                target.write_bytes(tiny)
            else:
                shutil.copyfile(PNG_SOURCE, target)
    return folder


class VerifierContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CONTAINER:
            raise unittest.SkipTest('set WH_CONTAINER to a running NVIDIA container')
        probe = subprocess.run(['docker', 'exec', CONTAINER, 'true'], capture_output=True)
        if probe.returncode != 0:
            raise unittest.SkipTest(f'container {CONTAINER} is not running')
        # The container fallback compares the live instance DB with instance_seed, so the
        # site must be at its seed state before the suite runs.
        control = os.environ.get('WH_CONTROL', 'http://127.0.0.1:20013')
        try:
            request = urllib.request.Request(f'{control}/reset/nvidia', method='POST')
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read())
            if not payload.get('ready'):
                raise unittest.SkipTest(f'container {CONTAINER} did not become ready after reset')
        except Exception as error:  # noqa: BLE001
            raise unittest.SkipTest(f'cannot reset {CONTAINER} through {control}: {error}')
        cls.work = Path(os.environ.get('TEST_OUT') or tempfile.mkdtemp(prefix='nvidia-contract-'))
        cls.work.mkdir(parents=True, exist_ok=True)

    def check(self, task_id, folder, extra=(), env_extra=None, expect=0):
        env = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
               'WH_CONTAINER': CONTAINER, 'HOME': os.environ.get('HOME', '/tmp')}
        env.update(env_extra or {})
        cmd = [sys.executable, '-B', str(VERIFY / f"verify_{task_id.split('--')[1]}.py"),
               '--run_dir', str(folder), *extra]
        result = subprocess.run(cmd, cwd=str(folder), env=env, capture_output=True, text=True, timeout=120)
        (folder / 'stdout.txt').write_text(result.stdout)
        (folder / 'stderr.txt').write_text(result.stderr)
        self.assertEqual(result.returncode, expect,
                         f'{cmd}\nexit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}')
        try:
            value = json.loads(result.stdout)
        except ValueError:
            self.fail(f'verifier stdout is not JSON: {result.stdout!r}')
        self.assertEqual(value['task_id'], 'NVIDIA--0')
        self.assertIs(value['pass'], expect == 0)
        if expect == 2:
            self.assertEqual(value.get('error'), 'INFRA_ERROR')
        return value

    def test_eval_judge_command_shape(self):
        """`eval_judge.py --verifier True` forwards only --run_dir."""
        folder = write_fixture(self.work / 'eval_judge_shape', production_shape_trajectory())
        self.check('NVIDIA--0', folder)

    def test_production_recorder_shape_without_task_json(self):
        folder = write_fixture(self.work / 'prod_no_taskjson', production_shape_trajectory())
        initial = self.work / 'prod_no_taskjson' / 'initial.db'
        after = self.work / 'prod_no_taskjson' / 'after.db'
        for name, dest in (('instance_seed', initial), ('instance', after)):
            subprocess.run(['docker', 'cp', f'{CONTAINER}:/opt/WebSyn/nvidia/{name}/nvidia.db', str(dest)],
                           check=True, capture_output=True)
        self.check('NVIDIA--0', folder, extra=('--initial_db', str(initial), '--after_db', str(after)))

    def test_legacy_no_llm_flag_accepted(self):
        folder = write_fixture(self.work / 'no_llm', production_shape_trajectory())
        self.check('NVIDIA--0', folder, extra=('--no_llm', 'True'))

    def test_loopback_host_spellings_are_the_same_origin(self):
        """localhost/127.0.0.1 on the same port is one origin (repair002, M9)."""
        trajectory = production_shape_trajectory()
        trajectory['steps'][1]['url'] = trajectory['steps'][1]['url'].replace('127.0.0.1', 'localhost')
        folder = write_fixture(self.work / 'loopback_aliases', trajectory)
        self.check('NVIDIA--0', folder)

    def test_different_run_port_is_rejected(self):
        trajectory = production_shape_trajectory()
        trajectory['steps'][1]['url'] = trajectory['steps'][1]['url'].replace(':21113', ':40028')
        folder = write_fixture(self.work / 'port_change', trajectory)
        self.check('NVIDIA--0', folder, expect=1)

    def test_non_loopback_origin_is_rejected(self):
        trajectory = production_shape_trajectory()
        trajectory['steps'].append({**trajectory['steps'][0], 'step': len(trajectory['steps']),
                                    'url': 'https://marketplace.nvidia.com/en-us/consumer/graphics-cards/'})
        folder = write_fixture(self.work / 'off_origin', trajectory)
        self.check('NVIDIA--0', folder, expect=1)

    def test_unreachable_container_is_structured_infra(self):
        folder = write_fixture(self.work / 'bad_container', production_shape_trajectory())
        self.check('NVIDIA--0', folder, extra=('--container', 'wh107-nvidia-nonexistent'), expect=2)

    def test_task_id_mismatch_is_infra(self):
        folder = write_fixture(self.work / 'bad_id', production_shape_trajectory('NVIDIA--1'))
        self.check('NVIDIA--0', folder, expect=2)

    def test_altered_question_is_infra(self):
        trajectory = production_shape_trajectory()
        trajectory['task'] = trajectory['task'] + ' (changed)'
        folder = write_fixture(self.work / 'bad_query', trajectory)
        self.check('NVIDIA--0', folder, expect=2)

    def test_altered_task_json_is_infra(self):
        trajectory = production_shape_trajectory()
        folder = write_fixture(self.work / 'bad_taskjson', trajectory, with_task_json=True)
        row = dict(TASKS['NVIDIA--0'])
        row['ques'] = row['ques'] + ' (changed)'
        (folder / 'task.json').write_text(json.dumps(row, indent=2) + '\n')
        self.check('NVIDIA--0', folder, expect=2)

    def test_matching_task_json_is_accepted(self):
        folder = write_fixture(self.work / 'good_taskjson', production_shape_trajectory(), with_task_json=True)
        self.check('NVIDIA--0', folder)


if __name__ == '__main__':
    unittest.main()
