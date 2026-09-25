"""Offline deterministic grading entrypoint for WebMD's 20 tasks.

Every run supplies trajectory.json, referenced screenshots, initial.db and
 after.db. Explicit --initial_db/--after_db paths are supported; Docker and
external LLM services are never consulted by the primary grader.
"""
import argparse
import json
import sqlite3

from answers import answer_ok
from evidence import Evidence, state_ok
from navigation import navigation_ok


def evaluate(task, run_dir, initial_db=None, after_db=None):
    result = {'task_id': f'WebMD--{task}', 'pass': False, 'reason': '', 'evidence': []}
    try:
        e = Evidence(run_dir, initial_db, after_db)
        checks = [
            ('task_identity', e.traj.get('task_id', e.traj.get('id')) == result['task_id']),
            ('observed_navigation', navigation_ok(e, task)),
            ('precise_state_delta', state_ok(e, task)),
            ('answer_facts', answer_ok(task, e.traj.get('final_answer') or '', e.initial)),
        ]
        for name, passed in checks:
            result['evidence'].append(f"[{'PASS' if passed else 'FAIL'}] {name}")
            if not passed and not result['reason']:
                result['reason'] = name
        result['pass'] = all(ok for _, ok in checks)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as ex:
        result['reason'] = 'invalid_or_missing_evidence'
        result['evidence'].append(str(ex))
    # sqlite3.DatabaseError is deliberately handled as evidence failure too.
    except sqlite3.Error as ex:
        result['reason'] = 'invalid_snapshot'
        result['evidence'].append(str(ex))
    return result


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db')
    parser.add_argument('--after_db')
    parser.add_argument('--no_llm', nargs='?', const='True', default='True',
                        help='Compatibility option; primary grading is always offline.')
    args = parser.parse_args()
    verdict = evaluate(task, args.run_dir, args.initial_db, args.after_db)
    print(json.dumps(verdict, indent=2))
    raise SystemExit(0 if verdict['pass'] else 1)
