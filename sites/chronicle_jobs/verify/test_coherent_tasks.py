"""Decision and evidence controls, independent of browser-path implementation."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coherent_grade import check_mutation, claim_matches, valid_page_evidence


def test_request_parameters_are_not_observed_navigation():
    trajectory = {'start_url': 'http://localhost:40072/', 'steps': [
        {'url_after': 'http://localhost:40072/', 'params': {'url': 'http://localhost:40072/target'}}]}
    assert not valid_page_evidence(trajectory, '/target')


def test_wrong_port_is_not_target_evidence(tmp_path):
    from PIL import Image
    shot = tmp_path / 'frame.png'
    Image.new('RGB', (400, 300), 'white').save(shot)
    trajectory = {'start_url': 'http://localhost:40072/', '_shots': {'frame.png': shot},
                  'steps': [{'url_after': 'http://localhost:40073/target', 'screenshot_after': 'frame.png'}]}
    assert not valid_page_evidence(trajectory, '/target')
    trajectory['steps'][0]['url_after'] = 'http://localhost:40072/target'
    assert valid_page_evidence(trajectory, '/target')


def test_exact_state_preserves_unrelated_rows():
    before = {'saved_jobs': [{'id': 1, 'user_id': 1, 'job_id': 10}, {'id': 2, 'user_id': 2, 'job_id': 11}],
              'users': [{'id': 1, 'headline': 'original'}]}
    after = copy.deepcopy(before)
    after['saved_jobs'].append({'id': 3, 'user_id': 1, 'job_id': 1467})
    spec = {'table': 'saved_jobs', 'add': {'user_id': 1, 'job_id': 1467}}
    assert check_mutation(before, after, spec)
    wrong = copy.deepcopy(after); wrong['saved_jobs'][-1]['job_id'] = 216
    assert not check_mutation(before, wrong, spec)
    wrong = copy.deepcopy(after); wrong['saved_jobs'][1]['job_id'] = 1467
    assert not check_mutation(before, wrong, spec)
    wrong = copy.deepcopy(after); wrong['users'][0]['headline'] = 'changed'
    assert not check_mutation(before, wrong, spec)
    assert not check_mutation(before, after, None)


def test_precise_removals_do_not_accept_emptying_shortlist():
    before = {'saved_jobs': [{'id': i} for i in range(1, 6)]}
    spec = {'table': 'saved_jobs', 'remove_ids': [2, 3, 4]}
    assert check_mutation(before, {'saved_jobs': [{'id': 1}, {'id': 5}]}, spec)
    assert not check_mutation(before, {'saved_jobs': []}, spec)

def test_salary_decision_binds_location_to_amount():
    specs = json.loads(Path(__file__).with_name('coherent_tasks.json').read_text())['3']['claims']
    good = 'Provost in Parker, Colorado pays $400,000. Provost & Chief Academic Officer in Loudonville, New York pays $300,000. Parker pays $100,000 more.'
    assert all(claim_matches(good, p) for p in specs)
    assert all(claim_matches(good.replace('$400,000', '400,000 dollars').replace('$300,000', 'USD 300,000'), p) for p in specs)
    wrong = good.replace('400,000', 'SWAP').replace('300,000', '400,000').replace('SWAP', '300,000')
    assert not all(claim_matches(wrong, p) for p in specs)
