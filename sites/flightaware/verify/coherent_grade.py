"""Task-specific decisions, page evidence and exact state deltas for revised tasks.

The frozen expectations live in coherent_tasks.json, never in agent-facing tasks.
No action-count threshold is imposed: difficulty must come from the task itself.
"""
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from verify_lib import final_answer


def claim_matches(answer, pattern):
    """Accept prose or tables; don't accept a quoted, denied answer as success."""
    answer = re.sub(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|dollars)\b", r"$\1", answer, flags=re.I)
    answer = re.sub(r"\bUSD\s*", "$", answer, flags=re.I)
    def calendar(match):
        try:
            return date.fromisoformat(match.group()).strftime('%B %d, %Y').replace(' 0', ' ')
        except ValueError:
            return match.group()
    answer = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", calendar, answer)
    for match in re.finditer(pattern, answer, re.I):
        preceding = re.split(r'[;\n.!?]', answer[:match.start()])[-1]
        if re.search(r'\b(?:incorrect|wrong|false|not true|do not choose|don.t choose|not|never)\s*[:=-]?\s*$', preceding, re.I):
            continue
        return True
    return False


def snapshot(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: [dict(row) for row in db.execute('SELECT * FROM "' + name + '" ORDER BY 1')] for name in names}


def valid_page_evidence(t, required):
    start = urlsplit(t.get('start_url', ''))
    for step in t.get('steps', []):
        # Only observed arrival URLs count. A requested URL is not navigation evidence.
        u = urlsplit(step.get('url_after') or step.get('url', ''))
        path = u.path.rstrip('/')
        target = required.rstrip('/')
        if (u.scheme, u.netloc) != (start.scheme, start.netloc):
            continue
        if path != target and not path.startswith(target + '/') and not (target.startswith('/photos/view/') and path.startswith(target + '-')):
            continue
        name = step.get('screenshot_after')
        shot = t.get('_shots', {}).get(name)
        if shot is None:
            continue
        try:
            with Image.open(shot) as im:
                im.load()
                if im.format == 'PNG' and im.width >= 200 and im.height >= 120:
                    return True
        except (OSError, ValueError, SyntaxError):
            pass
    return False


def check_mutation(before, after, spec):
    if not spec:
        return before == after
    table = spec['table']
    if set(before) != set(after) or any(before[k] != after[k] for k in before if k != table):
        return False
    old, new = before[table], after[table]
    if 'remove_ids' in spec:
        return new == [r for r in old if r['id'] not in spec['remove_ids']]
    added = [r for r in new if r not in old]
    return (all(r in new for r in old) and len(new) == len(old) + 1 and len(added) == 1
            and all(added[0].get(k) == v for k, v in spec['add'].items()))


def check(number, j, t, initial_db, after_db):
    config = json.loads(Path(__file__).with_name('coherent_tasks.json').read_text())
    spec = config.get(str(number))
    if spec is None:
        return False
    site = Path(__file__).resolve().parents[1].name
    if site == 'chronicle_jobs':
        from verify_lib import check_trajectory_identity, validate_snapshot_contract
        check_trajectory_identity(j, t, j.task_id)
        try:
            validate_snapshot_contract(initial_db, after_db)
        except (ValueError, OSError, sqlite3.Error) as error:
            j.check('snapshot_contract', False, str(error))
    else:
        j.bind_run(t)
    current = [json.loads(line) for line in Path(__file__).parents[1].joinpath('tasks.jsonl').read_text().splitlines()]
    expected_task = next(task for task in current if task['id'] == j.task_id)
    j.check('current_task_wording', t.get('task') == expected_task['ques'], 'evidence records the current task revision')
    for path in spec['paths']:
        j.check('nav_observed_page_' + path, valid_page_evidence(t, path), 'decoded screenshot after arrival at ' + path)
    answer = final_answer(t)
    for index, pattern in enumerate(spec['claims']):
        j.check('decision_or_support_' + str(index), claim_matches(answer, pattern), pattern)
    observations = '\n'.join(str(step.get(key) or '') for step in t.get('steps', [])
                             for key in ('observed_text', 'observed_text_after'))
    for pattern in spec.get('seen', []):
        j.check('entity_visible', bool(re.search(pattern, observations, re.I)), pattern)
    for pattern in spec.get('reject', []):
        j.check('no_contradiction', not re.search(pattern, answer, re.I), pattern)
    try:
        j.check('exact_saved_state' if spec.get('mutation') else 'db_readonly', check_mutation(snapshot(initial_db), snapshot(after_db), spec.get('mutation')),
                'only the requested saved-state delta; all unrelated rows and tables preserved')
    except (OSError, sqlite3.Error, TypeError) as error:
        j.check('saved_state_readable', False, str(error))
    return True
