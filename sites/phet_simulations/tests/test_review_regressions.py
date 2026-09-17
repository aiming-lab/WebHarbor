"""Reproducible regressions for PR #29/#114. No frozen private bundle required."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest
from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE / 'verify'))
import verify_lib as v


@pytest.fixture(scope='module')
def app_module(tmp_path_factory):
    isolated = tmp_path_factory.mktemp('phet')
    for name in ['app.py', 'catalog_data.py', '_health.py']:
        shutil.copy2(SITE / name, isolated / name)
    shutil.copytree(SITE / 'templates', isolated / 'templates')
    (isolated / 'static').symlink_to(SITE / 'static', target_is_directory=True)
    if (SITE / 'instance_seed/phet_simulations.db').exists():
        (isolated / 'instance').mkdir()
        shutil.copy2(SITE / 'instance_seed/phet_simulations.db', isolated / 'instance/phet_simulations.db')
    sys.path.insert(0, str(isolated))
    spec = importlib.util.spec_from_file_location('phet_review_app', isolated / 'app.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.app.config.update(TESTING=True)
    yield mod
    with mod.app.app_context():
        mod.db.session.remove()
        mod.db.engine.dispose()


def soup(client, url):
    response = client.get(url)
    assert response.status_code == 200, url
    return BeautifulSoup(response.data, 'html.parser')


def titles(page):
    return [n.get_text(strip=True) for n in page.select('.sim-title')]


def test_homepage_has_three_real_rails(app_module):
    page = soup(app_module.app.test_client(), '/')
    assert len(page.select('.sim-card')) == 20
    assert 'Recently Updated' in page.get_text()


def test_functional_filters_and_customize(app_module):
    client = app_module.app.test_client()
    page = soup(client, '/simulations?subject=biology&grade=elementary')
    assert set(titles(page)) == {'Color Vision', 'Density', 'Natural Selection'}
    assert '12 results' in soup(client, '/simulations?release=new').get_text()
    assert '9 results' in soup(client, '/simulations?topic=heat-and-thermo').get_text()
    assert len(titles(soup(client, '/simulations?view=customize'))) == 49
    assert 'Build an Atom' in titles(soup(client, '/search?q=build+atom'))
    assert len(page.select('input[name=language]')) == 132
    assert not page.select('input[type=checkbox]')  # each facet is explicitly single-select
    assert not page.select('input[name=compat], input[name=inclusive]')


def test_updated_filter_uses_update_date(app_module):
    with app_module.app.app_context():
        expected = app_module.Simulation.query.filter(app_module.Simulation.updated_date >= app_module.date(2024, 1, 1)).count()
        old_but_updated = app_module.Simulation.query.filter(app_module.Simulation.release_date < app_module.date(2024, 1, 1), app_module.Simulation.updated_date >= app_module.date(2024, 1, 1)).count()
    assert old_but_updated > 0
    page = soup(app_module.app.test_client(), '/simulations?release=updated')
    assert page.select_one('.results-count').get_text(strip=True) == f'{expected} results'


def test_filter_links_preserve_topic(app_module):
    from urllib.parse import parse_qs, urlsplit
    page = soup(app_module.app.test_client(), '/simulations?subject=physics&topic=motion&grade=high&language=en&release=updated')
    links = page.select('.results-chip a')
    assert len(links) == 5
    for link in links:
        if link.get('aria-label') != 'Clear topic':
            assert parse_qs(urlsplit(link['href']).query)['topic'] == ['motion']


def test_real_goals_and_no_card_answer_leak(app_module):
    client = app_module.app.test_client()
    page = soup(client, '/simulation/build-an-atom')
    with app_module.app.app_context():
        goals = app_module.Simulation.query.filter_by(slug='build-an-atom').one().learning_goals
    for goal in goals.split('<br/>'):
        assert BeautifulSoup(goal, 'html.parser').get_text() in page.get_text()
    assert 'Predict how changes to one parameter affect the rest of the system.' not in page.get_text()
    assert all(n.get('aria-label') == 'Translations available' for n in soup(client, '/simulations').select('.lang-dots'))


def test_all_get_routes_leave_database_unchanged(app_module):
    client = app_module.app.test_client()
    before = hashlib.sha256(app_module.DB_PATH.read_bytes()).hexdigest()
    paths = ['/', '/simulations', '/simulations?view=browse', '/simulations?view=customize', '/simulations?page=invalid', '/search?q=quantum', '/translations', '/teachers', '/teachers/activities', '/about', '/accessibility', '/login', '/register']
    with app_module.app.app_context():
        paths += ['/simulation/' + r.slug for r in app_module.Simulation.query.all()]
        paths += ['/translations/' + r.code for r in app_module.Language.query.all()]
        paths += ['/teachers/activity/' + str(r.id) for r in app_module.Activity.query.all()]
    for path in paths:
        soup(client, path)
    assert hashlib.sha256(app_module.DB_PATH.read_bytes()).hexdigest() == before
    with app_module.app.app_context():
        app_module.seed_all()
    assert hashlib.sha256(app_module.DB_PATH.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('table,sql', [
    ('user', "UPDATE user SET name='changed' WHERE id=1"),
    ('saved_simulation', "UPDATE saved_simulation SET notes='changed' WHERE id=1"),
    ('simulation', "UPDATE simulation SET version='0.0.0' WHERE id=1"),
    ('language', "UPDATE language SET sim_count=0 WHERE id=1"),
])
def test_same_row_count_writes_are_rejected(app_module, tmp_path, table, sql):
    after = tmp_path / 'after.db'; shutil.copy2(app_module.DB_PATH, after)
    with sqlite3.connect(after) as con:
        con.execute(sql)
    assert not v.read_only_run(app_module.DB_PATH, after)


@pytest.mark.parametrize('text,value,noun,expected', [
    ('9 simulations', 9, 'simulation', True),
    ('difference of 73.', 73, 'difference', True),
    ('nine simulations', 9, 'simulation', True),
    ('Simulations: 9', 9, 'simulation', True),
    ('119 simulations', 9, 'simulation', False),
    ('version 9.9.9 simulations', 9, 'simulation', False),
    ('120 subjects, 5 simulations', 120, 'simulation', False),
    ('14 activities', 14, 'activities', True),
])
def test_counts_bind_to_correct_value_and_noun(text, value, noun, expected):
    assert v.counts(text, value, noun) == expected


@pytest.mark.parametrize('url,expected', [
    ('http://localhost:40035/simulation/build-an-atom', True),
    ('http://127.0.0.1:55035/simulation/build-an-atom', True),
    ('https://evil.example/simulation/build-an-atom', False),
    ('http://localhost:40035/search?q=/simulation/build-an-atom', False),
    ('http://localhost:40035/simulation/build-an-atom-fake', False),
])
def test_navigation_cannot_match_decoy_urls(url, expected):
    assert v.navigated_to({'steps': [{'url': url}]}, '/simulation/build-an-atom') == expected


def test_exact_save_delta_rejects_unrelated_edits(app_module, tmp_path):
    initial = app_module.DB_PATH
    after = tmp_path / 'after.db'; shutil.copy2(initial, after)
    with sqlite3.connect(after) as con:
        user = con.execute("SELECT id FROM user WHERE email='student@phet.test'").fetchone()[0]
        sim = con.execute("SELECT id FROM simulation WHERE slug='membrane-transport'").fetchone()[0]
        con.execute('INSERT INTO saved_simulation(user_id,sim_id,notes) VALUES(?,?,?)', (user,sim,'review note'))
    assert v.exact_save_delta(initial, after, 'student@phet.test', 'membrane-transport', require_note=True)
    with sqlite3.connect(after) as con:
        con.execute("UPDATE user SET name='unrelated change' WHERE id=1")
    assert not v.exact_save_delta(initial, after, 'student@phet.test', 'membrane-transport', require_note=True)


def test_auth_csrf_save_notes_and_account_isolation(app_module):
    mod=app_module; client=mod.app.test_client(); before=mod.DB_PATH.read_bytes()
    def token(path):
        return soup(client,path).select_one('[name=csrf_token]')['value']
    try:
        assert client.post('/login',data={'email':'student@phet.test','password':'phet-student-pass'}).status_code==400
        csrf=token('/login')
        response=client.post('/login?next=https://example.com/',data={'email':'student@phet.test','password':'phet-student-pass','csrf_token':csrf})
        assert response.status_code==302 and response.location=='/account'
        page=soup(client,'/simulation/membrane-transport'); csrf=page.select_one('[name=csrf_token]')['value'];sim=int(page.select_one('.save-form')['data-sim-id'])
        headers={'X-CSRFToken':csrf}
        assert client.post('/api/save-sim',json={'sim_id':sim}).status_code==400
        for payload in [{'sim_id':'not-an-id'}, {'sim_id':sim,'notes':['invalid']}, ['invalid']]:
            assert client.post('/api/save-sim',json=payload,headers=headers).status_code==400
        assert client.post('/api/unsave-sim',json={'sim_id':'invalid'},headers=headers).status_code==400
        assert client.post('/api/save-sim',json={'sim_id':sim,'notes':'  lesson note  '},headers=headers).json['ok']
        assert v.saved_rows_for(mod.DB_PATH,'student@phet.test')==[('membrane-transport','lesson note')]
        assert len(v.saved_sims_for(mod.DB_PATH,'teacher@phet.test'))==4
        assert client.post('/api/save-sim',json={'sim_id':sim,'notes':'lesson note'},headers=headers).json['ok']
        assert len(v.saved_rows_for(mod.DB_PATH,'student@phet.test'))==1
        assert client.post('/api/unsave-sim',json={'sim_id':sim},headers=headers).json['ok']
        assert v.saved_rows_for(mod.DB_PATH,'student@phet.test')==[]
    finally:
        with mod.app.app_context():
            mod.db.session.remove();mod.db.engine.dispose()
        mod.DB_PATH.write_bytes(before)
