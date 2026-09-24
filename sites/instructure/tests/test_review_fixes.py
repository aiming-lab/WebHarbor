"""Regressions for resource query replacement, sourced event filters and local login returns."""
import os
import shutil
import sys
import importlib
from pathlib import Path
import pytest
SITE = Path(__file__).resolve().parents[1]
@pytest.fixture()
def client(tmp_path):
    scratch = tmp_path / 'instructure.db'
    shutil.copy2(SITE/'instance_seed/instructure.db', scratch)
    os.environ['INSTRUCTURE_DB_PATH'] = 'sqlite:///' + str(scratch)
    sys.path.insert(0, str(SITE))
    import app
    importlib.reload(app)
    try:
        yield app.app.test_client()
    finally:
        os.environ.pop('INSTRUCTURE_DB_PATH', None)

def test_search_field_not_duplicated(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(client.get('/resources/case-studies?hubs_search=Helena').data, 'html.parser')
    assert len(soup.select('[name=hubs_search]')) == 1
    assert soup.select_one('[name=hubs_search]')['type'] == 'text'
    result = client.get('/resources/case-studies?hubs_search=Edison').get_data(as_text=True)
    assert 'Search: Edison' in result

def test_event_regions_and_past_dates(client):
    html = client.get('/events?region=Asia%E2%80%93Pacific').get_data(as_text=True)
    assert 'BETT Asia' in html and 'National VET' in html
    assert 'Fall Administrators Conference' not in html
    import app
    with app.app.app_context():
        row = app.Event.query.filter_by(slug='bett-asia-0').one()
        row.event_date = 'Sep 01, 2026'
        app.db.session.commit()
    assert 'BETT Asia' in client.get('/events?time=Past').get_data(as_text=True)
    assert 'BETT Asia' not in client.get('/events').get_data(as_text=True)

def test_login_preserves_return_form(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(client.get('/login?next=/account/saved').data, 'html.parser')
    assert '/account/saved' in soup.select_one('main form')['action']

import pytest
@pytest.mark.parametrize('target', ['https://example.org/', '//example.org/', '/%2fexample.org/', '/\\example.org/', '/%0aevil', 'http://[bad'])
def test_external_return_rejected(target, client):
    import app as module
    assert module.local_return(target, '/account') == '/account'

@pytest.mark.parametrize('target', ['/account/saved', '/resources/case-studies?hubs_search=Helena'])
def test_local_return_kept(target, client):
    import app as module
    assert module.local_return(target, '/account') == target
