"""Regression checks for the reviewed TED mirror."""
from __future__ import annotations
import ast
import re
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SITE_DIR=Path(__file__).resolve().parents[1]
ROOT=SITE_DIR.parents[1]
SEED=SITE_DIR/'instance_seed'/'ted.db'

class EnvironmentQualityTests(unittest.TestCase):
 def test_site_registration_and_task_port(self):
  startup=(ROOT/'websyn_start.sh').read_text();control=(ROOT/'control_server.py').read_text();docker=(ROOT/'Dockerfile').read_text()
  sites=re.search(r'SITES=\((.*?)\)',startup,re.S).group(1).split()
  control_sites=next(ast.literal_eval(node.value) for node in ast.parse(control).body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='SITES' for target in node.targets))
  self.assertEqual(sites,control_sites);self.assertEqual(len(sites),len(set(sites)))
  self.assertEqual(sites.index('ted'),19)
  self.assertIn(f'EXPOSE 8101 40000-{40000+len(sites)-1}',docker)
  rows=[json.loads(line) for line in (SITE_DIR/'tasks.jsonl').read_text().splitlines() if line.strip()];self.assertEqual(len(rows),20)
  for i,row in enumerate(rows):self.assertEqual(row['id'],f'TED--{i}');self.assertEqual(row['web'],'http://localhost:40019/');self.assertEqual(row['verifier_path'],f'sites/ted/verify/verify_{i}.py');self.assertNotIn('answer',row)
 def test_asset_pin_is_immutable_and_ted_uses_shared_fetch_path(self):
  revision=next(line.split(':',1)[1].strip() for line in (ROOT/'.assets-revision').read_text().splitlines() if line.startswith('revision:'))
  script=(ROOT/'scripts/fetch_assets.sh').read_text();self.assertRegex(revision,r'^[0-9a-f]{40}$');self.assertNotIn('TED_ASSETS_REVISION',script);self.assertTrue(SEED.is_file())
 def test_seed_ground_truth(self):
  con=sqlite3.connect(SEED)
  try:
   self.assertEqual(con.execute('select count(*) from talk').fetchone()[0],64);self.assertEqual(con.execute('select count(*) from user').fetchone()[0],4)
   facts={r[0]:(r[1],r[2],r[3]) for r in con.execute("select slug,duration_seconds,views,event from talk where slug in ('anil-seth-why-ai-is-unlikely-to-become-conscious','peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent','nayeema-raza-3-habits-to-practice-curiosity-and-escape-your-phone','kate-canales-the-accidental-brilliance-of-makeshift-signs')")}
   self.assertEqual(facts['anil-seth-why-ai-is-unlikely-to-become-conscious'],(897,191682,'TED2026'));self.assertEqual(facts['peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent'],(1055,551544,'TED2026'));self.assertEqual(551544-191682,359862);self.assertEqual(554563-203431,351132)
  finally:con.close()
 def test_migration_is_idempotent(self):
  with tempfile.TemporaryDirectory(prefix='ted-migration-') as temp:
   database=Path(temp)/'ted.db';shutil.copy2(SEED,database);con=sqlite3.connect(database)
   try:
    con.execute('DROP INDEX uq_saved_talk_user_talk');con.execute('DROP INDEX uq_registration_user_event');con.commit()
   finally:con.close()
   command=[sys.executable,str(SITE_DIR/'migrate_seed.py'),str(database)];first=subprocess.run(command,capture_output=True,text=True,check=True);first_hash=hashlib.sha256(database.read_bytes()).hexdigest();second=subprocess.run(command,capture_output=True,text=True,check=True);second_hash=hashlib.sha256(database.read_bytes()).hexdigest();self.assertIn('2 indexes created',first.stdout);self.assertIn('0 indexes created',second.stdout);self.assertEqual(first_hash,second_hash)
 def test_post_forms_have_csrf_tokens(self):
  missing=[]
  for template in (SITE_DIR/'templates').glob('*.html'):
   lines=template.read_text().splitlines()
   for i,line in enumerate(lines):
    if '<form' in line and 'method="post"' in line.lower() and 'csrf_token' not in '\n'.join(lines[i:i+7]):missing.append(f'{template.name}:{i+1}')
  self.assertEqual(missing,[])
 def test_no_demo_credentials_or_get_logout(self):
  templates='\n'.join(p.read_text() for p in (SITE_DIR/'templates').glob('*.html'));self.assertNotIn('value="alice.j@test.com"',templates);self.assertNotIn('value="TestPass123!"',templates);self.assertNotIn("href=\"{{ url_for('logout') }}\"",templates)
 def test_exact_views_and_combined_topic_filter_are_visible(self):
  detail=(SITE_DIR/'templates/talk_detail.html').read_text();talks=(SITE_DIR/'templates/talks.html').read_text();self.assertIn('talk.exact_views_label',detail);self.assertIn('select name="topic"',talks);self.assertIn('name="event"',talks);self.assertIn('name="max_minutes"',talks)
 def test_read_only_tasks_declare_complete_database_check(self):
  for task in (0,2,3,5,6,8,10,11,13,14,15,17,18,19):self.assertIn('check_read_only', (SITE_DIR/f'verify/verify_{task}.py').read_text(),task)
if __name__=='__main__':unittest.main()
