"""Local account return and cosmetic sorting regressions."""
from bs4 import BeautifulSoup

def test_most_skins_sort(client):
    soup = BeautifulSoup(client.get('/champions/?sort=skins').data, 'html.parser')
    assert [x.get_text(strip=True) for x in soup.select('.champ-name')[:5]] == ['Miss Fortune', 'Lux', 'Ahri', 'Akali', 'Ezreal']

def test_ability_and_skin_controls_are_buttons(client):
    soup = BeautifulSoup(client.get('/champions/yunara/').data, 'html.parser')
    assert len(soup.select('button.ability-slot')) == 5
    assert len(soup.select('button.skin-thumb')) == 3

import pytest
@pytest.mark.parametrize('target', ['https://example.org/', '//example.org/', '/%2fexample.org/', '/\\example.org/', '/%0aevil', 'http://[bad'])
def test_external_return_rejected(target, client):
    import app as module
    assert module.local_return(target, '/account') == '/account'

@pytest.mark.parametrize('target', ['/account/saved', '/resources/case-studies?hubs_search=Helena'])
def test_local_return_kept(target, client):
    import app as module
    assert module.local_return(target, '/account') == target
