"""Offline grading primitives. Saved snapshots are mandatory; never use live DBs.

Text checks cover documented field-labelled answers and natural equivalents, not
arbitrary natural language. The independent LLM judge remains secondary.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, unquote, urlsplit


def norm(value):
    return re.sub(r'\s+', ' ', str(value).casefold().replace('–', '-').replace('—', '-')).strip()


def has(text, value):
    return bool(re.search(r'(?<!\w)' + re.escape(norm(value)) + r'(?!\w)', norm(text)))


def number(value):
    value = float(value)
    whole = int(value)
    if value == whole:
        forms = [str(whole), f'{whole:,}']
        if whole >= 1000 and whole % 1000 == 0:
            forms.append(f'{whole // 1000}k')
        return r'(?<![\d.,])(?:' + '|'.join(map(re.escape, forms)) + r')(?:\.0+)?(?!\d|[.,]\d)'
    return r'(?<![\d.,])(?:' + re.escape(f'{value:g}') + '|' + re.escape(f'{value:,.2f}') + r')(?!\d|[.,]\d)'


def money(text, value):
    return bool(re.search(r'\$\s*' + number(value) + r'|' + number(value) + r'\s*(?:dollars|usd)\b', norm(text)))


def measure(text, value, unit):
    return bool(re.search(number(value) + r'\s*(?:' + unit + r')\b', norm(text)))


def field(text, label, value):
    """Short label/value relationship, allowing label-first prose or value-first lines."""
    text = norm(text)
    bridge = r'[\s:=$()*-]*(?:(?:is|of|at|was|rating|price|costs?|maximum|up to|the|has)\s+)*'
    return bool(re.search(r'(?:' + label + r')' + bridge + number(value), text)
                or re.search(number(value) + r'(?:\s*/\s*5)?[\s:=$()*-]*(?:' + label + r')\b', text))


def date_in(text, iso):
    d = date.fromisoformat(str(iso)[:10])
    forms = [d.isoformat(), f'{d.month}/{d.day}/{d.year}',
             f'{d.strftime("%B")} {d.day}, {d.year}', f'{d.strftime("%b")} {d.day}, {d.year}',
             f'{d.day} {d.strftime("%B")} {d.year}']
    return any(has(text, form) for form in forms)


def snapshot(path):
    if not path.is_file():
        raise ValueError(f'Missing saved snapshot: {path}')
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {table: [dict(row) for row in db.execute('SELECT * FROM "' + table.replace('"', '""') + '"')]
                for table in tables}


class Review:
    def __init__(self, task, args):
        self.task = task
        self.run = Path(args.run_dir)
        self.traj = json.loads((self.run / 'trajectory.json').read_text())
        self.answer = self.traj.get('final_answer', '') or ''
        self.initial = snapshot(Path(args.initial_db) if args.initial_db else self.run / 'initial.db')
        self.after = snapshot(Path(args.after_db) if args.after_db else self.run / 'after.db')
        self.expected = {t: [dict(r) for r in rows] for t, rows in self.initial.items()}
        self.evidence = []
        self.failures = []
        self.check('nonempty answer', bool(self.answer.strip()))
        self.check('task identity', self.traj.get('task_id') == f'CarMax--{task}')

    def check(self, name, condition):
        self.evidence.append(f'{"PASS" if condition else "FAIL"}: {name}')
        if not condition:
            self.failures.append(name)
        return bool(condition)

    def nav(self, path, query=None):
        origin = urlsplit(self.traj.get('start_url', ''))
        for step in self.traj.get('steps', []):
            url = urlsplit(step.get('url', ''))
            if (url.scheme, url.netloc) != (origin.scheme, origin.netloc):
                continue
            if unquote(url.path).rstrip('/') != path.rstrip('/'):
                continue
            if query and not query(parse_qs(url.query)):
                continue
            shot = step.get('screenshot_after') or step.get('screenshot_before')
            if shot and (self.run / 'screenshots' / Path(shot).name).is_file():
                return True
        return False

    def require_nav(self, path, query=None):
        return self.check('visited ' + path, self.nav(path, query))

    def row(self, table, **where):
        rows = [r for r in self.initial[table] if all(r[k] == v for k, v in where.items())]
        if not rows:
            raise ValueError(f'Fixture missing {table}: {where}')
        return rows[0]

    def additions(self, table):
        old = {r['id'] for r in self.initial[table]}
        return [r for r in self.after[table] if r['id'] not in old]

    def added(self, table, wanted=1):
        rows = self.additions(table)
        self.check(f'exactly {wanted} new {table}', len(rows) == wanted)
        self.expected[table].extend(rows)
        return rows

    def fields(self, row, **expected):
        for name, value in expected.items():
            self.check(f'{name} = {value!r}', row.get(name) == value)

    def vehicle_answer(self, vehicle, trim=False):
        fields = ['year', 'make', 'model'] + (['trim'] if trim else [])
        self.check('vehicle identity', all(has(self.answer, vehicle[k]) for k in fields))

    def store_answer(self, store, name=False):
        self.check('store location', has(self.answer, store['city']) or has(self.answer, store['name']))
        if name:
            self.check('store name', has(self.answer, store['name']))

    def finish(self):
        def rows(items):
            return Counter(json.dumps(r, sort_keys=True) for r in items)
        self.check('table set preserved', self.expected.keys() == self.after.keys())
        for table, expected in self.expected.items():
            self.check('exact authorized delta: ' + table, rows(expected) == rows(self.after.get(table, [])))
        return {'task_id': f'CarMax--{self.task}', 'pass': not self.failures,
                'reason': '; '.join(self.failures), 'evidence': self.evidence}


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db', default='')
    parser.add_argument('--after_db', default='')
    parser.add_argument('--no_llm', nargs='?', default='True')  # compatibility; never skips checks
    parser.add_argument('--container', default='')  # retained CLI compatibility; no live fallback
    args = parser.parse_args()
    try:
        from rules import evaluate
        review = Review(task, args)
        evaluate(review)
        verdict = review.finish()
    except (OSError, ValueError, KeyError, sqlite3.Error, IndexError) as exc:
        verdict = {'task_id': f'CarMax--{task}', 'pass': False,
                   'reason': 'Invalid or incomplete evidence: ' + str(exc), 'evidence': []}
    print(json.dumps(verdict, indent=2))
    raise SystemExit(0 if verdict['pass'] else 1)
