#!/usr/bin/env python3
"""verify_lib.py — deterministic verifier utilities for sec task
verification (reviewer contract, orch/review/sec).

Philosophy: DETERMINISTIC FIRST. No LLM call is load-bearing; every check is
regex / token / SQLite after-state.

  1. Package identity (fail-closed): task_id matches, ``terminated`` with
     ``agent_done``, non-empty final answer, every recorded URL on the same
     loopback origin AND port as ``start_url``, every referenced screenshot a
     decodable PNG.
  2. Seed identity gate (fail-closed): the initial DB snapshot must BE the
     frozen in-image seed (file sha256 + per-table counts + schema digest +
     rows digest). A run graded against a pre-mutated database fails here.
  3. Navigation gates (anti knowledge-shortcut): the agent MUST have opened
     the on-site surfaces the task names (company pages with their form
     filters, full-text search, enforcement lists and detail pages, FAST
     Answers, forms index, rulemaking, the tip/complaint/question forms,
     account). A correct answer with no matching navigation is a
     memory-recall shortcut = FAIL.
  4. Answer check: affirmative token / phrase / number matching against
     ground truth HARDCODED in each ``verify_<n>.py`` (never in tasks.jsonl),
     plus ``forbidden`` patterns that reject fabricated values for question
     points the rendered site does not carry and stale/wrong claims.
  5. DB after-state: read-only tasks require every table row-identical to
     the seed; stateful tasks require the exact allowed row delta and
     nothing else. Runtime-generated reference numbers (TCR-*, IC-*, Q-*)
     are checked for shape and linkage via regex matchers, never frozen
     literals.

Seed reproducibility: the sec seed is rebuilt deterministically inside the
pinned image (PYTHONHASHSEED=0, frozen bcrypt benchmark password) by the
real Dockerfile sec site block (469-asset inventory gate -> deterministic
seed -> instance_seed freeze -> seed-database check). The review image
(webharbor:sec-review, built independently by the reviewer from
orch/contribute/sec @ e7067e37) reproduces the seed byte-identically with
the contributor's declared in-image seed; every per-task reset snapshot is
byte-identical.

Input signature (per task):
  --run_dir DIR        agent trajectory dir: trajectory.json + screenshots/
  --initial_db PATH    initial-state SQLite DB (default: <run_dir>/initial.db)
  --after_db PATH      after-state  SQLite DB (default: <run_dir>/after.db)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS,
1 on FAIL.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

SITE = "sec"

# tasks.jsonl is the single source of task text; a trajectory recorded against
# a stale or foreign question must fail closed.
_TASKS_FILE = Path(__file__).resolve().parent.parent / 'tasks.jsonl'
_TASKS = {json.loads(line)['id']: json.loads(line)['ques']
          for line in _TASKS_FILE.read_text().splitlines() if line.strip()}

# ---- frozen seed identity (computed from the in-image instance_seed) -------
SEED_SHA256 = "59d95b8d5903063b0bbea21f38e57e31be4f06416d52cf397fa14f779e4d9e4b"
SEED_COUNTS = {"admin_proceedings": 100, "companies": 50, "complaints": 1, "email_subscriptions": 0, "fast_answers": 15, "filings": 1666, "form_index": 153, "fts_docs": 80, "investor_alerts": 9, "lit_releases": 100, "press_releases": 100, "questions": 1, "rulemakings": 49, "speeches": 25, "tips": 1, "trading_suspensions": 100, "users": 4, "watchlist_items": 7, "whats_new": 20}
SEED_SCHEMA_SHA256 = "0824c85d8f7def9e3348434a92acf4009c3053f7a70765fe43a77ca5797e1458"
SEED_ROWS_SHA256 = "2e2465a1468a98ea64217490e94e6d680d63abfdfb758e50d203db8f7fa7cd55"


def norm(text):
    """Normalize an answer string for deterministic matching."""
    text = str(text).replace('|', ' ').replace('**', '').casefold()
    for a, b in (('\u201d', '"'), ('\u201c', '"'), ('\u2019', "'"),
                ('\u2013', '-'), ('\u2014', '-'), ('\u2212', '-'),
                ('\u00ae', ''), ('\u2122', ''), ('\u2120', ''),
                ('\u00b7', ' '), ('\u2026', '...'), ('\u00a0', ' ')):
        text = text.replace(a, b)
    text = re.sub(r'(?<=\d),(?=\d)', '', text)          # 1,074,984.36 -> 1074984.36
    text = re.sub(r'\$\s*', '$', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def load_db(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing saved database: ' + path.name)
    con = sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Corrupt database: ' + path.name)
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        data = {}
        schema_parts = []
        for t in tables:
            cols = [(r[1], r[2]) for r in con.execute(f'PRAGMA table_info("{t}")')]
            schema_parts.append([t, cols])
            pk = [r[1] for r in sorted(con.execute(f'PRAGMA table_info("{t}")'),
                                       key=lambda r: r[5]) if r[5]]
            keys = pk or [c[0] for c in cols]
            rows = {}
            for r in con.execute(f'SELECT * FROM "{t}"'):
                d = dict(r)
                rows[json.dumps([d[k] for k in keys], default=str)] = d
            data[t] = rows
        return data, schema_parts
    finally:
        con.close()


def db_counts(data):
    return {t: len(rows) for t, rows in data.items()}


def schema_digest(schema_parts):
    return hashlib.sha256(json.dumps(
        schema_parts, sort_keys=True, default=str).encode()).hexdigest()


def rows_digest(data):
    payload = [[t, [[k, row] for k, row in rows.items()]]
               for t, rows in sorted(data.items())]
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, default=str).encode()).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def png_ok(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.format == 'PNG'
    except Exception:
        return False


class Fail(Exception):
    pass


def check_package(run, spec):
    if run.get('task_id') != spec['task_id']:
        raise Fail(f"task_id mismatch: {run.get('task_id')!r} != "
                   f"{spec['task_id']!r}")
    if run.get('task') != _TASKS.get(spec['task_id']):
        raise Fail('task text does not match tasks.jsonl '
                   '(stale or foreign question)')
    if not run.get('terminated'):
        raise Fail('trajectory not terminated')
    if run.get('termination_reason') != 'agent_done':
        raise Fail('termination_reason is not agent_done')
    answer = run.get('final_answer') or ''
    if not str(answer).strip():
        raise Fail('empty final answer')
    start = urlsplit(run.get('start_url') or '')
    if start.hostname not in ('localhost', '127.0.0.1'):
        raise Fail('start_url is not loopback: ' + str(run.get('start_url')))
    port = start.port or 80
    urls = []
    for step in run.get('steps') or []:
        for key in ('url', 'url_before', 'url_after'):
            u = (step or {}).get(key)
            if u:
                urls.append(u)
    for u in urls:
        if u == 'about:blank':
            continue  # the fresh tab's pre-navigation URL, not a target
        p = urlsplit(u)
        if p.hostname not in ('localhost', '127.0.0.1') or \
                (p.port or 80) != port:
            raise Fail('off-origin or cross-port URL in trajectory: ' + u)
    shots = set()
    for step in run.get('steps') or []:
        for key in ('screenshot_before', 'screenshot_after', 'screenshot'):
            s = (step or {}).get(key)
            if s:
                shots.add(s)
    if not shots:
        raise Fail('no screenshots in trajectory')
    for s in sorted(shots):
        p = Path(run.get('_run_dir', '.')) / 'screenshots' / s
        if not p.is_file():
            raise Fail('missing screenshot: ' + s)
        if not png_ok(p):
            raise Fail('screenshot is not a decodable PNG: ' + s)
    return urls


def check_seed(initial_db):
    if file_sha256(initial_db) != SEED_SHA256:
        raise Fail('initial database is not the frozen seed '
                   '(sha256 ' + file_sha256(initial_db)[:16] + '...)')
    data, schema = load_db(initial_db)
    counts = db_counts(data)
    if counts != SEED_COUNTS:
        raise Fail('seed table counts differ: ' + json.dumps(counts))
    if schema_digest(schema) != SEED_SCHEMA_SHA256:
        raise Fail('seed schema digest differs')
    if rows_digest(data) != SEED_ROWS_SHA256:
        raise Fail('seed rows digest differs')
    return data


def check_navigation(urls, spec):
    joined = '\n'.join(urls)
    for pattern in spec.get('paths', []):
        if not re.search(pattern, joined, re.I):
            raise Fail('navigation gate: required surface not visited: '
                       + pattern)


def check_answer(answer, spec):
    text = norm(answer)
    for label, pattern in spec.get('claims', []):
        if not re.search(pattern, text, re.I):
            raise Fail(f'answer claim missing: {label} (pattern {pattern!r})')
    for label, pattern in spec.get('forbidden', []):
        if re.search(pattern, text, re.I):
            raise Fail(f'answer contains fabricated/forbidden value '
                       f'for: {label}')


def row_matches(row, expect):
    """expect: dict of column matchers (value, regex:, one_of:, bcrypt_password:,
    min_len:). Byte values are decoded before matching."""
    for col, want in expect.items():
        if col not in row:
            return False
        value = row[col]
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='replace')
        if isinstance(want, dict):
            if 'regex' in want:
                if re.fullmatch(want['regex'], str(value), re.I) is None:
                    return False
            elif 'one_of' in want:
                if str(value) not in want['one_of']:
                    return False
            elif 'bcrypt_password' in want:
                import bcrypt
                try:
                    if not bcrypt.checkpw(want['bcrypt_password'].encode(),
                                           str(value).encode()):
                        return False
                except (ValueError, TypeError):
                    return False
            elif 'min_len' in want:
                if len(str(value)) < want['min_len']:
                    return False
            else:
                return False
        elif str(value) != str(want):
            return False
    return True


def _consume_one_to_one(rows, expects, table, kind):
    """Consume expected row matchers one-to-one against changed rows.

    Multiplicity is load-bearing on both sides: ``rows`` carries one entry
    per changed row (a content key repeated twice yields two entries) and
    every entry must claim a distinct expected matcher (Kuhn's augmenting
    path). A duplicated row can therefore never satisfy two expectations,
    and two identical new rows are never accepted as a single required
    addition (or removal)."""
    if len(rows) != len(expects):
        raise Fail(f'{kind}-row count mismatch in {table}: '
                    f'{len(rows)} != {len(expects)}')
    matched_to = [-1] * len(expects)   # expected index -> row index

    def augment(r, seen):
        for e, exp in enumerate(expects):
            if seen[e] or not row_matches(rows[r], exp):
                continue
            seen[e] = True
            if matched_to[e] == -1 or augment(matched_to[e], seen):
                matched_to[e] = r
                return True
        return False

    for r in range(len(rows)):
        if not augment(r, [False] * len(expects)):
            raise Fail(f'unexpected {kind} row in {table}: '
                        + json.dumps(rows[r], default=str)[:300])


def check_state(initial, after, spec):
    # Diff by content multiset, ignoring the volatile rowid column 'id':
    # the site reuses SQLite rowids after deletes, so PK-keyed diffs would
    # misclassify a delete+insert as a row mutation (seen in watchlist_items).
    # Added/removed rows are expanded by the per-key integer count difference
    # (a key added twice yields two entries) and then consumed one-to-one
    # against the expected matchers, so state multiplicity is preserved:
    # duplicating a changed row can never pass as the exact required delta.
    def counts(rows):
        c = {}
        for row in rows.values():
            key = json.dumps({k: v for k, v in row.items() if k != 'id'},
                             default=str, sort_keys=True)
            c[key] = c.get(key, [0, row])
            c[key][0] += 1
        return c

    diffs = {}
    for table in sorted(set(initial) | set(after)):
        i_rows = counts(initial.get(table, {}))
        a_rows = counts(after.get(table, {}))
        added, removed = [], []
        for k, (n, row) in a_rows.items():
            added.extend([row] * max(n - i_rows.get(k, (0,))[0], 0))
        for k, (n, row) in i_rows.items():
            removed.extend([row] * max(n - a_rows.get(k, (0,))[0], 0))
        if added or removed:
            diffs[table] = {'added': added, 'removed': removed,
                            'changed': []}
    allowed = spec.get('state', {})
    for table, delta in diffs.items():
        if table not in allowed:
            raise Fail('unexpected DB change in table ' + table + ': '
                      + json.dumps(delta, default=str)[:400])
        _consume_one_to_one(delta['added'],
                            allowed[table].get('added', []),
                            table, 'added')
        _consume_one_to_one(delta['removed'],
                            allowed[table].get('removed', []),
                            table, 'removed')
        if delta['changed']:
            raise Fail('unexpected row mutation in ' + table + ': '
                       + json.dumps(delta['changed'], default=str)[:300])
    # every allowed delta must actually be present
    for table, delta in allowed.items():
        if table not in diffs:
            raise Fail('expected state change missing in table ' + table)


def verify(run_dir, spec):
    run_dir = Path(run_dir)
    traj_path = run_dir / 'trajectory.json'
    if not traj_path.is_file():
        raise Fail('missing trajectory.json')
    run = json.loads(traj_path.read_text())
    run['_run_dir'] = str(run_dir)
    initial_db = Path(os.environ['WH_INITIAL_DB']) if \
        os.environ.get('WH_INITIAL_DB') else run_dir / 'initial.db'
    after_db = Path(os.environ['WH_AFTER_DB']) if \
        os.environ.get('WH_AFTER_DB') else run_dir / 'after.db'
    evidence = []
    urls = check_package(run, spec)
    evidence.append('package identity ok')
    initial = check_seed(initial_db)
    evidence.append('seed identity ok (sha256 ' + SEED_SHA256[:16] + '...)')
    check_navigation(urls, spec)
    evidence.append('navigation gates ok')
    check_answer(run.get('final_answer') or '', spec)
    evidence.append('answer claims ok')
    after, _schema = load_db(after_db)
    check_state(initial, after, spec)
    evidence.append('db after-state ok')
    return {
        'task_id': spec['task_id'],
        'pass': True,
        'reason': 'all contract checks passed',
        'evidence': evidence,
    }


def main(task_id, spec):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run_dir', required=True)
    ap.add_argument('--initial_db')
    ap.add_argument('--after_db')
    args = ap.parse_args()
    if args.initial_db:
        os.environ['WH_INITIAL_DB'] = args.initial_db
    if args.after_db:
        os.environ['WH_AFTER_DB'] = args.after_db
    try:
        result = verify(args.run_dir, spec)
    except Fail as e:
        print(json.dumps({'task_id': task_id, 'pass': False,
                          'reason': str(e), 'evidence': []}, indent=1))
        return 1
    except Exception as e:  # corrupt db / missing files etc.
        print(json.dumps({'task_id': task_id, 'pass': False,
                          'reason': f'hard failure: {e}', 'evidence': []},
                         indent=1))
        return 1
    print(json.dumps(result, indent=1))
    return 0
