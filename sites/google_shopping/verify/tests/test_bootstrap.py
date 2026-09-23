"""Fresh and populated bootstrap must share the canonical benchmark state."""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_canonical_bootstrap_and_sort_preservation(tmp_path):
    site = Path(__file__).resolve().parents[2]
    scratch = tmp_path / 'site'
    shutil.copytree(site, scratch, ignore=shutil.ignore_patterns(
        'instance', 'instance_seed', 'static', '__pycache__'))
    def run(code):
        result = subprocess.run([sys.executable, '-c', code], cwd=scratch,
                                text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
    run('import app')
    database = scratch / 'instance/google_shopping.db'
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT user_id,product_id FROM saved_items').fetchall() == [(1,28)]
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    run('import app')
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    run('''from app import app
from bs4 import BeautifulSoup
client=app.test_client()
page=BeautifulSoup(client.get('/search?q=trench&sort=price_desc').data,'html.parser')
assert page.select_one('.filters input[name=sort]')['value']=='price_desc'
assert page.select_one('.filters button').find_parent('label') is None
response=client.post('/login?next=https://example.com/',data={'email':'alice.j@test.com','password':'TestPass123!'})
assert response.headers['Location']=='/'
''')
