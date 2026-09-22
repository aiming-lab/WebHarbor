#!/usr/bin/env python3
"""IRS graders: observed same-origin pages, natural answers, frozen DB deltas."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import parse_qs, unquote, urlsplit

from answers import answer_ok, norm

TASK_COUNT = 18
STATEFUL_TASKS = {8}
LOOKUPS = {0: 'WMR-2024-8554', 1: 'WMR-2025-8776', 2: 'WMR-2023-8887',
           3: 'WMR-2024-9009', 10: 'WMR-2025-8665', 11: 'WMR-2025-8221',
           12: 'WMR-2025-8776', 13: 'WMR-2024-8554', 17: 'WMR-2023-8887'}
ACCOUNTS = {6: 'Bob Chen', 7: 'Alice Johnson', 8: 'David Kim',
            9: 'Carol Davis', 16: 'Alice Johnson'}
REQUIRED_TABLES = {'users', 'taxpayer_profiles', 'tax_returns', 'refund_statuses',
                   'lookup_histories', 'search_logs', 'filing_statuses', 'notices',
                   'help_articles', 'faqs', 'document_checklist_items', 'alerts',
                   'refund_timeline_events'}


def load_run(run_dir):
    root = Path(run_dir)
    traj = json.loads((root / 'trajectory.json').read_text())
    # Older review recorders saved observed body text alongside screenshots.
    # Never use a final answer/thought/action description as observed page text.
    for step in traj.get('steps', []):
        if 'page_text' not in step and isinstance(step.get('step'), int):
            sidecar = root / f"page_{step['step']:03d}.txt"
            if sidecar.is_file():
                step['page_text'] = sidecar.read_text()
    return traj


def origin(url):
    try:
        p = urlsplit(url)
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            return None
        return p.scheme, p.hostname.lower(), p.port or (443 if p.scheme == 'https' else 80)
    except (TypeError, ValueError):
        return None


def observed_pages(traj):
    expected = origin(traj.get('start_url', ''))
    if expected is None:
        return []
    pages = []
    for step in traj.get('steps', []):
        url = step.get('url', '')
        if origin(url) != expected:
            continue
        p = urlsplit(url)
        pages.append((unquote(p.path).rstrip('/') or '/', parse_qs(p.query),
                      norm(step.get('page_text', ''))))
    return pages


def navigation_ok(task, traj):
    pages = observed_pages(traj)
    paths = {p for p, _, _ in pages}

    def content(path, *tokens):
        return any(p == path and all(norm(t) in text for t in tokens)
                   for p, _, text in pages)

    def search(term):
        return any(p == '/search' and len(q.get('q', [])) == 1
                   and re.search(term, norm(q['q'][0])) and text
                   for p, q, text in pages)

    if task in LOOKUPS:
        if not {'/refund-status/start', '/refund-status/verify', '/refund-status/result'} <= paths:
            return False, 'lookup form steps/result not observed on the start origin'
        if task == 10:
            valid_result = content('/refund-status/result', 'Malik Rivera', 'Information Mismatch',
                                   'the ZIP code does not match')
        else:
            valid_result = content('/refund-status/result', 'refund status result', LOOKUPS[task])
        if task == 13:
            valid_result &= search(r'\bsplit\b')
        if task == 17:
            valid_result &= content('/refund-status/summary', 'printable summary', LOOKUPS[task], 'paper check')
        return bool(valid_result), 'required case/result content and optional search/summary'
    if task in ACCOUNTS:
        if '/login' not in paths:
            return False, 'sign-in page not visited'
        account = ACCOUNTS[task]
        if task == 8:
            return ('/account/edit' in paths and content('/account', account, 'Spokane', 'Email')), 'David profile edit and saved account page'
        allowed = ['/lookup-history'] if task in {9, 16} else ['/lookup-history', '/account']
        return any(content(p, account) for p in allowed), 'requested account identity on its history/account page'
    if task == 4:
        return bool(search(r'\bamend\w*\b') and content('/help/amended-return-wait-times', 'amended', 'longer')), 'relevant search and timing article'
    if task == 5:
        return ('/notices' in paths and content('/notices/ID-221', 'ID-221', 'checklist', 'contact preference')), 'notice list and ID-221 detail'
    if task == 14:
        return any(p == '/notices' and q.get('stage') == ['Refund Sent'] and 'sp-177' in text for p,q,text in pages), 'Refund Sent notice filter and allocation code'
    if task == 15:
        return content('/faq', 'saved lookup history is tied to local benchmark or registered demo accounts'), 'expanded history FAQ answer'
    return False, 'unknown task'


def snapshot(path):
    if not path or not Path(path).is_file():
        raise ValueError('required database snapshot missing')
    result = {}
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        schema = db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        for table, ddl in schema:
            quoted = table.replace('"', '""')
            columns = [r[1] for r in db.execute(f'PRAGMA table_info("{quoted}")')]
            if 'id' not in columns:
                raise ValueError('table without stable row identity')
            rows = [dict(row) for row in db.execute(f'SELECT * FROM "{quoted}"')]
            indexed = {row['id']: row for row in rows}
            if len(indexed) != len(rows):
                raise ValueError('duplicate row identity')
            result[table] = {'schema': ddl, 'rows': indexed}
    if not REQUIRED_TABLES <= result.keys():
        raise ValueError('incomplete site snapshot schema')
    return result


def state_ok(task, initial_db, after_db):
    try:
        before, after = snapshot(initial_db), snapshot(after_db)
        expected = deepcopy(before)
        if task == 8:
            david = [r for r in expected['users']['rows'].values() if r.get('email') == 'david.k@test.com']
            if len(david) != 1 or (david[0].get('city'), david[0].get('preferred_contact_method')) != ('Seattle', 'Mail'):
                return False, 'David initial profile is not the benchmark starting state'
            david[0].update(city='Spokane', preferred_contact_method='Email')
        else:
            # Searches and signed-in lookups may append logging rows. They may
            # neither edit/delete existing rows nor change domain/user data.
            for table in ['search_logs', 'lookup_histories']:
                old = before[table]['rows']
                new = after.get(table, {}).get('rows', {})
                if any(new.get(k) != v for k,v in old.items()):
                    return False, f'pre-existing {table} rows changed'
                if any(k <= max(old, default=0) for k in new.keys()-old.keys()):
                    return False, f'non-appended {table} identity'
                expected[table]['rows'] = new
        return expected == after, 'only requested profile fields / permitted append-only logs may differ'
    except (ValueError, sqlite3.Error, OSError, KeyError, TypeError) as exc:
        return False, f'invalid snapshots: {exc}'


def evaluate(task_index, traj, initial_db='', after_db='', **_unused):
    if not 0 <= task_index < TASK_COUNT:
        raise ValueError('unknown task')
    nav, nav_detail = navigation_ok(task_index, traj)
    state, state_detail = state_ok(task_index, initial_db, after_db)
    answer = str(traj.get('final_answer') or '').strip()
    checks = [('required_navigation', nav, nav_detail),
              ('answer_claim', answer_ok(task_index, answer), answer),
              ('snapshot_delta', state, state_detail)]
    passed = all(ok for _,ok,_ in checks)
    return {'task_id': f'IRS Refund Tracker--{task_index}', 'pass': passed,
            'reason': next((name for name,ok,_ in checks if not ok), ''),
            'evidence': [f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}" for name,ok,detail in checks]}


def main(task_index):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db', default='')
    parser.add_argument('--after_db', default='')
    # Accepted for older callers, but never used as a mutable DB fallback.
    parser.add_argument('--container', default='')
    parser.add_argument('--no_llm', nargs='?', const='True', default='True')
    args = parser.parse_args()
    root = Path(args.run_dir)
    try:
        verdict = evaluate(task_index, load_run(root),
                           args.initial_db or root/'initial.db',
                           args.after_db or root/'after.db')
    except (OSError, ValueError, TypeError) as exc:
        verdict = {'task_id': f'IRS Refund Tracker--{task_index}', 'pass': False,
                   'reason': 'invalid_evidence', 'evidence': [str(exc)]}
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict['pass'] else 1)
