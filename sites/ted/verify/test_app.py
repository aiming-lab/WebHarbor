"""HTTP-level regression tests for the TED mirror."""
from __future__ import annotations
import importlib
import os
import re
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

SITE_DIR=Path(__file__).resolve().parents[1]
SEED=SITE_DIR/'instance_seed'/'ted.db'
RUNTIME=SITE_DIR/'instance'/'ted.db'

def csrf_token(response)->str:
 match=re.search(rb'name="csrf_token" value="([^"]+)"',response.data)
 if not match:raise AssertionError(f'CSRF token missing from {response.request.path}')
 return match.group(1).decode()

class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  shutil.rmtree(SITE_DIR/'instance',ignore_errors=True);(SITE_DIR/'instance').mkdir();shutil.copy2(SEED,RUNTIME)
  os.environ['TED_SECRET_KEY']='test-only-secret'
  sys.path.insert(0,str(SITE_DIR));cls.module=importlib.import_module('app');cls.app=cls.module.app;cls.app.config.update(TESTING=True)
 @classmethod
 def tearDownClass(cls):
  with cls.app.app_context():cls.module.db.session.remove()
  shutil.rmtree(SITE_DIR/'instance',ignore_errors=True)
 def setUp(self):self.client=self.app.test_client()
 def login(self,email='alice.j@test.com',next_url=None):
  route='/login'+(f'?next={next_url}' if next_url else '');page=self.client.get(route);return self.client.post(route,data={'csrf_token':csrf_token(page),'email':email,'password':'TestPass123!'},follow_redirects=False)
 def snapshot(self):
  con=sqlite3.connect(RUNTIME)
  try:
   tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")];return {table:con.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}
  finally:con.close()
 def test_all_get_templates_render(self):
  paths=['/','/talks','/talks?topic=ai&event=TED2026&max_minutes=20','/search?q=AI','/topics','/playlists','/events','/login','/register','/_health']
  with self.app.app_context():
   paths += [f'/talks/{row.slug}' for row in self.module.Talk.query.all()];paths += [f'/playlists/{row.slug}' for row in self.module.Playlist.query.all()];paths += [f'/topics/{topic}' for topic in self.module.available_topics()]
  for route in paths:
   with self.subTest(route=route):self.assertEqual(self.client.get(route,follow_redirects=True).status_code,200)
 def test_csrf_and_logout_method(self):
  self.assertEqual(self.client.get('/logout').status_code,405)
  for route in ('/logout','/events','/account','/save/anil-seth-why-ai-is-unlikely-to-become-conscious'):
   with self.subTest(route=route):self.assertEqual(self.client.post(route).status_code,400)
 def test_external_login_redirect_is_rejected(self):
  response=self.login(next_url='//evil.invalid');self.assertEqual(response.status_code,302);self.assertEqual(response.headers['Location'],'/account')
 def test_login_page_does_not_disclose_credentials(self):
  body=self.client.get('/login').get_data(as_text=True);self.assertNotIn('alice.j@test.com',body);self.assertNotIn('TestPass123!',body)
 def test_combined_filters_and_exact_view_counts(self):
  body=self.client.get('/talks?topic=ai&event=TED2026&max_minutes=20').get_data(as_text=True);self.assertIn('Peter Steinberger',body);self.assertIn('Anil Seth',body)
  detail=self.client.get('/talks/peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent').get_data(as_text=True);self.assertIn('551,544',detail)
 def test_search_handles_simple_morphology(self):
  body=self.client.get('/search?q=architectures').get_data(as_text=True);self.assertIn('Riyad Joucka',body)
 def test_oversized_registration_is_rejected(self):
  response=self.client.post('/register',data=b'x'*(65*1024),content_type='application/x-www-form-urlencoded');self.assertEqual(response.status_code,413)
 def test_get_routes_leave_database_unchanged(self):
  before=self.snapshot()
  for route in ('/','/talks','/talks?topic=ai&event=TED2026&max_minutes=20','/search?q=AI','/topics','/events'):self.assertEqual(self.client.get(route).status_code,200)
  self.assertEqual(before,self.snapshot())
 def test_invalid_registration_is_rejected_without_state_change(self):
  before=self.snapshot();page=self.client.get('/register');response=self.client.post('/register',data={'csrf_token':csrf_token(page),'display_name':'','username':'!!!','email':'bad','password':'short'});self.assertEqual(response.status_code,400);self.assertEqual(before,self.snapshot())
if __name__=='__main__':unittest.main()
