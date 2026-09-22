"""Offline primary grading: saved evidence, exact navigation, precise DB deltas.

No network or Docker access occurs during grading. A missing snapshot is an
evidence error, never a silent switch to mutable live state.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from answers import answer_ok, norm
from state import snapshot, verify_delta

DETAILS = {
    0: ['yosemite-creek-campground', 'porcupine-flat-campground'],
    1: ['point-reyes-national-seashore-campground'],
    2: ['inyo-national-forest-wilderness-permits'],
    3: ['san-francisco-maritime-historic-park-tours', 'fort-point-national-historic-site-tours'],
    4: ['hemlock-cabin'], 5: ['apostle-islands-camping-permits'],
    9: ['yosemite-national-park-site-pass', 'denali-national-park-site-pass', 'grand-teton-national-park-site-pass'],
    10: ['voyageurs-national-park-tours'], 11: ['fort-point-national-historic-site-tours'],
    16: ['fort-point-national-historic-site-tours'], 17: ['cumberland-island-camping-permits'],
    18: ['aravaipa-canyon-wilderness-permits'], 19: ['yellowstone-national-park-fishing-permit'],
}
ROUTES = {6: ['/help'], 7: ['/articles/play-it-safe-trip-planning'],
          8: ['/articles/celebrate-america-250'], 11: ['/saved'],
          12: ['/checkout', '/reservations'], 13: ['/reservations'], 14: ['/account'],
          15: ['/register', '/account'], 19: ['/cart']}


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid mirror URL')
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)


def page_urls(trajectory):
    for step in trajectory.get('steps', []):
        if step.get('action_result', {}).get('error'):
            continue
        # The standard agent logs pre-action URL, newer recorders also save
        # post-action URL. Never use action.params.url as proof it loaded.
        for key in ('url', 'url_after'):
            value = step.get(key)
            if value:
                yield step, value


def navigate_check(task, trajectory, expected_origin=None):
    start = trajectory.get('start_url', '')
    allowed = origin(expected_origin or start)
    if origin(start) != allowed:
        raise ValueError('Run start URL differs from configured mirror')
    pages = []
    for step, url in page_urls(trajectory):
        try:
            if origin(url) == allowed:
                pages.append((step, urlsplit(url)))
        except ValueError:
            continue
    paths = {unquote(p.path).rstrip('/') or '/' for _, p in pages}
    required = ['/facility/' + slug for slug in DETAILS.get(task, [])] + ROUTES.get(task, [])
    if not all(path in paths for path in required):
        raise ValueError('Missing required on-site pages: ' + ', '.join(p for p in required if p not in paths))
    if task == 4:
        if not any(p.path == '/search' and (
                any('alaska' == norm(q) for q in parse_qs(p.query).get('q', []))
                or any(norm(q) in ('ak', 'alaska') for q in parse_qs(p.query).get('state', [])))
                   for _, p in pages):
            raise ValueError('Missing Alaska browse results')
    if task == 1:
        # Anchor navigation is available through View Photos. A recorder may
        # instead attest section visibility or an explicit successful scroll.
        viewed = any(p.path == '/facility/point-reyes-national-seashore-campground' and (
            p.fragment == 'media-gallery'
            or 'media-gallery' in step.get('visible_sections', [])
            or (step.get('action') == 'scroll' and '#media-gallery' in str(step.get('params', {}).get('target', '')))
        ) for step, p in pages)
        if not viewed:
            raise ValueError('Missing gallery viewing evidence (anchor/visible section/recorded scroll)')
    return True


def evaluate(task, run_dir, initial_db=None, after_db=None, expected_origin=None):
    evidence = []
    verdict = {'task_id': f'RecreationGov--{task}', 'pass': False, 'reason': '', 'evidence': evidence}
    try:
        run = Path(run_dir).resolve()
        trajectory = json.loads((run / 'trajectory.json').read_text())
        if trajectory.get('task_id') != verdict['task_id']:
            raise ValueError('Task ID mismatch')
        navigate_check(task, trajectory, expected_origin)
        evidence.append('Required on-site navigation and workflow evidence present')
        answer = trajectory.get('final_answer') or ''
        if not answer_ok(task, answer):
            raise ValueError('Answer does not establish the required affirmative facts/associations')
        evidence.append('Offline answer contract satisfied')
        initial = Path(initial_db).resolve() if initial_db else run / 'initial.db'
        after = Path(after_db).resolve() if after_db else run / 'after.db'
        if not initial.is_file() or not after.is_file():
            raise ValueError('Evidence error: both initial.db and after.db snapshots are required')
        verify_delta(task, snapshot(initial), snapshot(after), answer)
        evidence.append('Exact whole-database state delta satisfied using saved snapshots')
        verdict['pass'] = True
    except (OSError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        verdict['reason'] = str(exc)
    except Exception as exc:
        # Emit the grading contract on corrupt SQLite/schema input too.
        verdict['reason'] = f'Evidence error: {type(exc).__name__}: {exc}'
    return verdict


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--initial_db')
    parser.add_argument('--after_db')
    parser.add_argument('--origin', help='Optional trusted mirror origin; otherwise use runner-supplied start_url')
    parser.add_argument('--no_llm', nargs='?', const='True', help='Compatibility only: primary grading is always offline')
    parser.add_argument('--container', help='Deprecated compatibility option; live DBs are never read')
    args = parser.parse_args()
    verdict = evaluate(task, args.run_dir, args.initial_db, args.after_db, args.origin)
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict['pass'] else 1)
