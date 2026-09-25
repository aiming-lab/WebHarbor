"""Application regressions run against an isolated copy of the seeded mirror."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SITE = Path(__file__).resolve().parents[1]


def test_authentication_forms_and_seeded_landing_content(tmp_path):
    root = tmp_path / 'site'
    shutil.copytree(SITE, root, ignore=shutil.ignore_patterns('instance', 'images', '__pycache__'))
    (root / 'instance').mkdir()
    shutil.copy2(SITE / 'instance_seed/ohio_gov.db', root / 'instance/ohio_gov.db')
    code = r'''import app,re,json,hashlib
app.app.config['TESTING']=True
c=app.app.test_client()
assert c.post('/login',data={'email':'alice.j@test.com','password':'TestPass123!'}).status_code==400
assert c.get('/logout').status_code in (404,405)
for nxt in ['https://example.org','//example.org','/\\example.org']:
 c=app.app.test_client()
 token=re.search(r'name="csrf_token" value="([^"]+)"',c.get('/login').text)[1]
 r=c.post('/login',query_string={'next':nxt},data={'email':'alice.j@test.com','password':'TestPass123!','csrf_token':token})
 assert r.headers['Location']=='/account',r.headers
assert c.post('/account/edit',data={'city':'Changed'}).status_code==400
# Templates and runtime never need the build-time JSON once the seed exists.
import shutil
shutil.rmtree('data')
for route in ['/', '/residents', '/jobs', '/business', '/tourism', '/government', '/resources/driver-licenses']:
 assert c.get(route).status_code==200,route
app.app.config['WTF_CSRF_ENABLED']=False
with app.app.app_context(): before=app.AlertSubscription.query.count()
for _ in range(2): c.post('/alerts/subscribe',data={'email':'alice.j@test.com','alert_type':'Unemployment system'})
with app.app.app_context(): assert app.AlertSubscription.query.count()==before+1
assert c.post('/alerts/subscribe',data={'email':'alice.j@test.com','alert_type':'invalid'}).status_code==400
with app.app.app_context(): before=app.TravelGuideRequest.query.count()
c.post('/travel-guide',data={'full_name':'Test','email':'test@example.com','address_line1':'1 Main St','city':'Columbus','state':'Ohio','zip':'43215','format':'invalid'})
with app.app.app_context(): assert app.TravelGuideRequest.query.count()==before
print('all application regressions passed')
'''
    p = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
