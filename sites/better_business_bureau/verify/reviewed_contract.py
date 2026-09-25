"""Reviewed fixture and exact state-delta checks; no network or LLM calls."""
from pathlib import Path
import copy
import hashlib
import json
from urllib.parse import urlsplit, parse_qs
from verify_lib import rows, shot_at, step_text

CONTRACT = json.loads(Path(__file__).with_name('reviewed_contract.json').read_text())

def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def revised(number):
    return str(number) in CONTRACT.get('revised', {})

def check(judge, number, trajectory, initial, final):
    before, after = rows(initial), rows(final)
    judge.check('snapshots_available', before is not None and after is not None,
                'Both initial and final snapshots must be readable')
    if before is None or after is None:
        return
    hashes = {table: digest(data) for table, data in before.items()}
    judge.check('reviewed_initial_fixture', hashes == CONTRACT['initial_tables'],
                'Initial data must match the reviewed seed, including unrelated accounts')
    expected = copy.deepcopy(before)
    plan = CONTRACT.get('changes', {}).get(str(number), [])
    for operation in plan:
        table = operation['table']
        if table not in expected or table not in after:
            judge.check('state_table', False, table)
            return
        if operation['kind'] == 'insert':
            old_ids = {row['id'] for row in expected[table]}
            new = [row for row in after[table] if row['id'] not in old_ids]
            valid = len(new) == 1 and all(new[0].get(key) == value for key, value in operation['values'].items())
            judge.check('requested_insert', valid, f'Exactly one requested {table} record')
            if valid:
                expected[table].append(new[0])
                expected[table].sort(key=lambda row: row['id'])
        elif operation['kind'] == 'delete':
            expected[table] = [row for row in expected[table] if row['id'] != operation['id']]
        elif operation['kind'] == 'update':
            target = next((row for row in expected[table] if row['id'] == operation['id']), None)
            actual = next((row for row in after[table] if row['id'] == operation['id']), None)
            if target is None or actual is None:
                judge.check('requested_update', False, 'Target record missing')
                return
            target.update(operation['values'])
            for key in operation.get('runtime_fields', []):
                target[key] = actual[key]
    judge.check('exact_saved_state', expected == after,
                'Only requested inserts, deletions and field updates are permitted; preserve all other rows')
    supplement = CONTRACT.get('revised', {}).get(str(number), {})
    for path in supplement.get('pages', []):
        found = any(urlsplit(step.get('url', '')).path.rstrip('/') == path.rstrip('/') for step in trajectory.get('steps', []))
        judge.check('supplement_page_' + path, found and shot_at(trajectory, path)[0], path)
    if supplement.get('email'):
        judge.check('supplement_account', supplement['email'] in step_text(trajectory), supplement['email'])
