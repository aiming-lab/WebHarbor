"""Offline review contract: browser evidence, scoped claims, and exact state deltas.

Language recognition is finite and deterministic; no LLM and no live-state fallback.
Adapted from the WebHarbor disney/backcounty contract engine with subset row
matching so runtime-generated reference numbers (TCR-*, IC-*, Q-*) are checked
for shape and linkage, not for a frozen literal.
"""
import argparse
import bcrypt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit, unquote, parse_qs

from PIL import Image


def norm(text):
    text = str(text).replace('|', ' ').replace('**', '').casefold()
    text = (text.replace('−', '-').replace('®', '').replace('™', '')
                .replace('’', "'").replace('–', '-').replace('—', '-')
                .replace('&', 'and'))
    text = re.sub(r'(?<!\d):|:(?!\d)', ' ', text)
    text = re.sub(r'\busd\b\s*', '$', text)
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\b(?!-tone)',
                  lambda m: str(['zero', 'one', 'two', 'three', 'four', 'five',
                                 'six', 'seven', 'eight', 'nine', 'ten'].index(m.group(0))), text)
    for old, new in [(r'\bwi fi\b', 'wi-fi'), (r'\bpounds?\b', 'lb'),
                     (r'\bhrs?\b', 'hours'), (r'\bfree of charge\b', 'free')]:
        text = re.sub(old, new, text)
    return re.sub(r'\s+', ' ', text).strip()


def database(path):
    if not path.is_file():
        raise ValueError('Missing saved database: ' + path.name)
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Corrupt database')
        data = {}
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            keys = [r[1] for r in sorted(con.execute(f'PRAGMA table_info("{table}")'),
                                         key=lambda r: r[5]) if r[5]]
            data[table] = {json.dumps([r[k] for k in keys]): dict(r)
                           for r in con.execute(f'SELECT * FROM "{table}"')}
        return data


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                                      separators=(',', ':')).encode()).hexdigest()


def matches(value, expected):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='strict')
    if isinstance(expected, dict):
        if 'bcrypt_password' in expected:
            try:
                return bcrypt.checkpw(expected['bcrypt_password'].encode(),
                                      str(value).encode())
            except (ValueError, TypeError):
                return False
        if 'regex' in expected:
            return re.fullmatch(expected['regex'], str(value), re.I) is not None
        if 'one_of' in expected:
            return value in expected['one_of']
    return value == expected


def check_state(initial, after, spec):
    if digest(initial) != spec['initial_digest']:
        raise ValueError('Initial state does not match reviewed seed')
    if initial.keys() != after.keys():
        raise ValueError('Database tables changed')

    # Diff by content multiset, ignoring the volatile rowid column 'id':
    # the site reuses SQLite rowids after deletes, so PK-keyed diffs would
    # misclassify a delete+insert as a row mutation (seen in watchlist_items
    # when a removed row's id is immediately reused by the next insert).
    def counts(rows):
        c = {}
        for row in rows.values():
            key = json.dumps({k: v for k, v in row.items() if k != 'id'},
                             default=str, sort_keys=True)
            c.setdefault(key, [0, row])[0] += 1
        return c

    diffs = {}
    for table in sorted(set(initial) | set(after)):
        i_rows = counts(initial.get(table, {}))
        a_rows = counts(after.get(table, {}))
        added = [row for k, (n, row) in a_rows.items()
                 if i_rows.get(k, (0,))[0] < n]
        removed = [row for k, (n, row) in i_rows.items()
                   if a_rows.get(k, (0,))[0] < n]
        if added or removed:
            diffs[table] = {'added': added, 'removed': removed}

    allowed = spec.get('state', {})
    for table, delta in diffs.items():
        if table not in allowed:
            raise ValueError('Unexpected database change in ' + table + ': '
                             + json.dumps(delta, default=str)[:400])
        for row in delta['added']:
            if not any(set(exp) <= set(row) and
                       all(matches(row[k], v) for k, v in exp.items())
                       for exp in allowed[table].get('added', [])):
                raise ValueError('Incorrect new ' + table + ' row: '
                                 + json.dumps(row, default=str)[:300])
        if len(delta['added']) != len(allowed[table].get('added', [])):
            raise ValueError('Wrong number of new rows in ' + table)
        for row in delta['removed']:
            if not any(set(exp) <= set(row) and
                       all(matches(row[k], v) for k, v in exp.items())
                       for exp in allowed[table].get('removed', [])):
                raise ValueError('Unexpected removed ' + table + ' row: '
                                 + json.dumps(row, default=str)[:300])
        if len(delta['removed']) != len(allowed[table].get('removed', [])):
            raise ValueError('Wrong number of removed rows in ' + table)


def check_claims(answer, claims):
    text = norm(answer)
    if re.search(r'\b(?:not true|incorrect answer|ignore these facts|'
                 r'the following is false|these claims are false)\b', text):
        raise ValueError('Answer rejects its own claims')
    for label, pattern in claims:
        pattern = pattern.replace('pounds', 'lb').replace('hrs/day', 'hours/day')
        hits = list(re.finditer(pattern, text, re.I))
        if not hits:
            raise ValueError('Missing or incorrect ' + label)
        for m in hits:
            claim = m.group()
            claim = re.sub(r'\bnot yet rated\b', 'unrated', claim)
            claim = re.sub(r"\bnot (?:provided|available|shown|listed|captured|"
                           r"submitted|confirmed)\b(?!\s*$)", 'unavailable', claim)
            if re.search(r"\b(?:not|never|isn't|aren't|doesn't|don't|cannot)\b",
                         claim) and not re.search(r'not|never|ineligible|unavailable|prohibit',
                                                  pattern):
                raise ValueError('Contradicted ' + label)


def verify(run_dir, task_id):
    run = Path(run_dir).resolve()
    traj = json.loads((run / 'trajectory.json').read_text())
    spec = json.loads(Path(__file__).with_name('contract.json').read_text())[task_id]
    if traj.get('task_id') != task_id or traj.get('task', traj.get('ques')) != spec['task']:
        raise ValueError('Wrong task identity or wording')
    if not traj.get('terminated') or traj.get('termination_reason') != 'agent_done':
        raise ValueError('Unfinished attempt')
    start = urlsplit(traj.get('start_url', ''))
    if start.scheme not in ['http', 'https'] or start.hostname not in \
            ['localhost', '127.0.0.1', '::1']:
        raise ValueError('Invalid local start URL')
    origin = (start.scheme, start.hostname, start.port)
    urls = []
    seen = set()
    steps = traj.get('steps', [])
    if not steps:
        raise ValueError('Missing browser evidence')
    for step in steps:
        for key in ['url', 'url_before', 'url_after']:
            if key in step:
                u = urlsplit(step[key])
                if u.scheme == 'about':
                    continue  # the fresh tab's pre-navigation URL, not a target
                if (u.scheme, u.hostname, u.port) != origin:
                    raise ValueError('Browser evidence changes origin')
        u = urlsplit(step.get('url_after', step.get('url', '')))
        urls.append(unquote(u.path + ('?' + u.query if u.query else '')))
        name = step.get('screenshot_after', step.get('screenshot'))
        if not name or Path(name).name != name:
            raise ValueError('Invalid screenshot reference')
        path = run / 'screenshots' / name
        if path not in seen:
            with Image.open(path) as im:
                im.load()
                if im.format != 'PNG' or im.width < 320 or im.height < 200:
                    raise ValueError('Screenshot is not a full browser PNG')
                if len(im.convert('RGB').resize((32, 32)).getcolors(1024) or []) < 8:
                    raise ValueError('Blank browser screenshot')
            seen.add(path)
    for pattern in spec['paths']:
        if not any(re.search(pattern, u, re.I) for u in urls):
            raise ValueError('Required page evidence missing: ' + pattern)
    initial = database(run / 'initial.db')
    after = database(run / 'after.db')
    check_state(initial, after, spec)
    answer = traj.get('final_answer', '')
    check_claims(answer, spec['claims'])
    for pattern in spec.get('forbidden', []):
        if re.search(pattern, norm(answer), re.I):
            raise ValueError('Contradictory answer: ' + pattern)
    return {'task_id': task_id, 'pass': True,
            'reason': 'Browser evidence, factual claims and exact saved-state '
                      'contract passed',
            'evidence': [f'{len(seen)} decoded screenshots',
                         f'{len(spec["claims"])} checked claims',
                         'Saved initial and final databases compared']}


def main(task_id):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_dir', required=True)
    args = parser.parse_args()
    try:
        result = verify(args.run_dir, task_id)
    except Exception as exc:
        result = {'task_id': task_id, 'pass': False, 'reason': str(exc),
                  'evidence': []}
    print(json.dumps(result))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    if __name__ == '__main__' and len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        raise SystemExit(main(sys.argv[1]))
    raise SystemExit(main('SEC.gov--0'))
