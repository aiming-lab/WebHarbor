"""Declared positive/negative controls in copied evidence; never alters the preview."""
import argparse
import sys
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
BASE = args.runs.resolve()
REPO = Path(__file__).resolve().parents[3]
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=False)
ENV = {k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'JUDGE_MODEL')}
ENV['WH_CONTAINER'] = 'wh-pr66-deliberately-absent'
SEED = BASE / 'task-00/initial.db'
results = []

def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')

def case(n, name, expected, answer=None, url_mode=None, sql=None, baseline=False, official=False, task_id=None):
    source = BASE / f'task-{n:02d}'
    target = OUT / f'{n:02d}-{name}'
    target.mkdir()
    trajectory = json.loads((source / 'trajectory.json').read_text())
    origin = trajectory['start_url'].rstrip('/')
    if answer is not None:
        trajectory['final_answer'] = answer
    if task_id is not None:
        trajectory['task_id'] = task_id
    if url_mode == 'home':
        trajectory['steps'] = [{'action': 'navigate', 'url': origin + '/'}]
    elif url_mode == 'external':
        for step in trajectory['steps']:
            for key in ('url', 'url_before', 'url_after'):
                step[key] = step.get(key, '').replace(origin, 'https://unrelated.example')
    elif url_mode == 'slug-query':
        trajectory['steps'] = [{'action': 'navigate', 'url': origin + '/?q=hemlock-cabin'}]
    elif url_mode == 'two-passes':
        trajectory['steps'] = [s for s in trajectory['steps'] if 'grand-teton' not in s.get('url', '')]
    elif url_mode == 'no-gallery':
        trajectory['steps'] = [{'action': 'navigate', 'url': origin + '/facility/point-reyes-national-seashore-campground'}]
    elif url_mode == 'detail-only':
        trajectory['steps'] = [{'action': 'navigate', 'url': origin + '/facility/hemlock-cabin'}]
    trajectory['operator'] = 'Synthetic grading control; reused/source-derived facts, not a browser run'
    dump(target / 'trajectory.json', trajectory)
    for name_db in ('initial.db', 'after.db'):
        shutil.copy2(SEED if baseline else source / name_db, target / name_db)
    if sql:
        with sqlite3.connect(target / 'after.db') as conn:
            for statement in sql:
                conn.execute(statement)
    definition = {'task': n, 'case': name, 'expected': expected, 'answer': answer, 'url_mode': url_mode, 'sql_on_copied_after_db': sql, 'entrypoint': 'official evaluator without live container' if official else 'verifier CLI with explicit saved snapshots'}
    dump(target / 'control.json', definition)
    if official:
        command = ['uv', 'run', '--project', 'agent_demo', 'python', 'agent_demo/eval_judge.py', '--run_dir', str(target), '--verifier', 'True']
    else:
        command = [sys.executable, f'sites/recreation_gov/verify/verify_{n}.py', '--run_dir', str(target), '--initial_db', str(target / 'initial.db'), '--after_db', str(target / 'after.db')]
    run = subprocess.run(command, cwd=REPO, env=ENV, capture_output=True, text=True)
    (target / 'grade.log').write_text(run.stdout + run.stderr)
    verdict = json.loads((target / 'eval.json').read_text()) if official else json.loads(run.stdout)
    if not official:
        dump(target / 'eval.json', verdict)
    result = {**definition, 'actual': verdict.get('pass'), 'reason': verdict.get('reason'), 'path': str(target)}
    results.append(result)
    print(n, name, 'expected', expected, 'actual', result['actual'], flush=True)

for n in range(20):
    case(n, 'empty-noop', False, answer='', url_mode='home', baseline=True)
    case(n, 'saved-positive-explicit', True)
    if n in (11, 12, 13, 14, 15, 16, 19):
        case(n, 'saved-positive-official-no-container', True, official=True)

for n, name, answer in [
    (0, 'wrong-open-campground', 'Yosemite Creek Campground is closed. Porcupine Flat Campground is the open option and offers Hiking.'),
    (1, 'one-scene-only', 'A campsite.'),
    (2, 'wrong-parent', 'Inyo National Forest Wilderness Permits is in Yosemite National Park.'),
    (3, 'swapped-tour-attributes', 'Fort Point National Historic Site Tours highlights Historic Ships. San Francisco Maritime Historic Park Tours is part of Golden Gate National Recreation Area.'),
    (4, 'negated-cabin', 'It is not Hemlock Cabin.'),
    (5, 'wrong-classification', 'Kayaking is an activity. This is a campground, not a permit.'),
    (6, 'wrong-fee-kind', 'Campground reservations include the fee; ticket reservations do not.'),
    (7, 'unrelated-checks', 'Check inventory prices, your date of birth, and the advertising agency logo.'),
    (8, 'negated-places', 'The article does not mention Fort Point, Yosemite, or Denali.'),
    (9, 'wrong-pass-fee', 'Denali has the additional non-U.S. resident fee; Yosemite does not.'),
    (10, 'wrong-tour-parent', 'Voyageurs National Park Tours is part of Yellowstone National Park.'),
    (17, 'wrong-state', 'It is in Florida, not Georgia. Beach Camping is listed.'),
    (18, 'missing-permit-type', 'Hiking is listed, but only Day Use Permit, not Overnight Permit, is mentioned.'),
]:
    case(n, name, False, answer=answer)

case(4, 'off-origin-navigation', False, url_mode='external')
case(4, 'homepage-query-substring', False, url_mode='slug-query')
case(4, 'missing-state-browse', False, url_mode='detail-only')
case(4, 'wrong-task-id', False, task_id='RecreationGov--999')
case(9, 'missing-third-comparison', False, url_mode='two-passes')
case(1, 'gallery-never-viewed', False, url_mode='no-gallery')
case(18, 'concise-both-equivalent', True, answer='Hiking; both.')
case(7, 'equivalent-three-checks', True, answer='Check the type of reservation needed, permitted travel dates, and the managing authority’s rules.')

case(12, 'cancelled-new-reservation', False, sql=["UPDATE reservation SET status='Cancelled' WHERE user_id=(SELECT id FROM user WHERE email='bob.c@test.com') AND confirmation_code GLOB 'RG-2026-[0-9][0-9][0-9][0-9][0-9]'"])
case(12, 'wrong-price-and-dates', False, sql=["UPDATE reservation SET total_cost=0, start_date='2030-01-01', end_date='2030-01-02' WHERE user_id=(SELECT id FROM user WHERE email='bob.c@test.com') AND confirmation_code GLOB 'RG-2026-[0-9][0-9][0-9][0-9][0-9]'"])
case(13, 'yellowstone-price-changed', False, sql=["UPDATE reservation SET total_cost=0 WHERE confirmation_code='RG-2026-AJ02'"])
case(14, 'unrelated-account-change', False, sql=["UPDATE user SET home_city='Unrequested change' WHERE email='alice.j@test.com'"])
case(15, 'wrong-registration-identities', False, sql=["UPDATE user SET username='wrong_username', display_name='Wrong Name', password_hash='invalid' WHERE email='river.stone@example.com'"])
case(16, 'negated-review-note', False, sql=["UPDATE review SET body='It is not true that Accessible route was easy to follow.' WHERE author='David Kim' AND facility_id=(SELECT id FROM facility WHERE slug='fort-point-national-historic-site-tours') AND rating=4"])
case(19, 'existing-cart-deleted', False, sql=["DELETE FROM cart_item WHERE user_id=(SELECT id FROM user WHERE email='alice.j@test.com') AND facility_id=(SELECT id FROM facility WHERE slug='pinnacles-campground')"])
case(11, 'unrelated-saves-deleted', False, sql=["DELETE FROM saved_item WHERE user_id=(SELECT id FROM user WHERE email='alice.j@test.com') AND facility_id!=(SELECT id FROM facility WHERE slug='fort-point-national-historic-site-tours')"])
case(4, 'read-task-modifies-profile', False, sql=["UPDATE user SET phone='Unrequested' WHERE email='alice.j@test.com'"])

# Isolate the owner check: alter only the newly added review's user_id.
case(16, 'wrong-owner-only', False, sql=["UPDATE review SET user_id=(SELECT id FROM user WHERE email='alice.j@test.com') WHERE author='David Kim' AND rating=4 AND body='Accessible route was easy to follow.'"])
case(19, 'wrong-cart-quantity', False, sql=["UPDATE cart_item SET quantity=2 WHERE facility_id=(SELECT id FROM facility WHERE slug='yellowstone-national-park-fishing-permit') AND user_id=(SELECT id FROM user WHERE email='alice.j@test.com')"])
case(12, 'wrong-reservation-owner', False, sql=["UPDATE reservation SET user_id=(SELECT id FROM user WHERE email='alice.j@test.com') WHERE confirmation_code GLOB 'RG-2026-[0-9][0-9][0-9][0-9][0-9]'"])
case(13, 'other-reservation-deleted', False, sql=["DELETE FROM reservation WHERE confirmation_code='RG-2026-AJ02'"])
case(15, 'wrong-default-city', False, sql=["UPDATE address SET city='Boston' WHERE user_id=(SELECT id FROM user WHERE email='river.stone@example.com')"])
dump(OUT / 'control-results.json', results)
summary = {'count': len(results), 'matched': sum(r['expected'] == r['actual'] for r in results), 'false_accepts': sum(r['expected'] is False and r['actual'] is True for r in results), 'false_rejects_or_replay_failures': sum(r['expected'] is True and r['actual'] is False for r in results)}
dump(OUT / 'control-summary.json', summary)
print(summary, flush=True)
raise SystemExit(0 if summary['matched'] == summary['count'] else 1)
