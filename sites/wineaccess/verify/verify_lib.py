#!/usr/bin/env python3
"""WineAccess deterministic grading from observed UI and immutable run snapshots."""
import argparse
import json
import sqlite3
from pathlib import Path
from answers import answer_ok
from navigation import navigation_ok
from state import read_db, transition

STATEFUL_TASKS = {0, 1, 4, 5, 7, 10, 13, 14, 16}
TASK_COUNT = 18


def evaluate(index, traj, initial_db=None, after_db=None):
    result = {'task_id': f'Wine Access--{index}', 'pass': False, 'evidence': []}
    try:
        if traj.get('task_id') != result['task_id']:
            return dict(result, reason='task_id_mismatch')
        if not initial_db or not after_db:
            return dict(result, reason='run_snapshots_required')
        before, after = read_db(initial_db), read_db(after_db)
        ok, reason, ctx = transition(index, before, after)
        if not ok:
            return dict(result, reason=reason)
        result['evidence'].append(reason)
        if not navigation_ok(index, traj, before, after, ctx):
            return dict(result, reason='required_observed_navigation')
        result['evidence'].append('same_origin_task_pages_observed')
        if not answer_ok(index, str(traj.get('final_answer') or ''), ctx):
            return dict(result, reason='answer_not_supported')
        return dict(result, **{'pass': True, 'reason': 'verified'})
    except (OSError, ValueError, KeyError, StopIteration, TypeError, sqlite3.Error) as exc:
        return dict(result, reason='invalid_evidence:' + type(exc).__name__)


def main(index):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db')
    parser.add_argument('--after_db')
    args = parser.parse_args()
    run = Path(args.run_dir)
    try:
        traj = json.loads((run / 'trajectory.json').read_text())
        result = evaluate(index, traj, args.initial_db or run / 'initial.db', args.after_db or run / 'after.db')
    except (OSError, ValueError) as exc:
        result = {'task_id': f'Wine Access--{index}', 'pass': False, 'reason': 'invalid_trajectory:' + type(exc).__name__, 'evidence': []}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['pass'] else 1
