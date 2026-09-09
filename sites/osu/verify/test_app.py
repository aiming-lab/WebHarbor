"""HTTP regression tests for the OSU mirror."""
from __future__ import annotations
import importlib,os,re,shutil,sqlite3,sys,unittest
from pathlib import Path
from sites.osu.verify.test_support import ensure_seed
SITE=Path(__file__).resolve().parents[1];SEED=ensure_seed();RUNTIME=SITE/'instance/osu.db'
def csrf(response):
 m=re.search(rb'name="csrf_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="csrf_token"',response.data);assert m,response.request.path;return (m.group(1) or m.group(2)).decode()
class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  shutil.rmtree(SITE/'instance',ignore_errors=True);(SITE/'instance').mkdir();shutil.copy2(SEED,RUNTIME);os.environ['OSU_SECRET_KEY']='test-only';sys.path.insert(0,str(SITE));cls.module=importlib.import_module('app');cls.app=cls.module.app;cls.app.config.update(TESTING=True)
 @classmethod
 def tearDownClass(cls):
  with cls.app.app_context():cls.module.db.session.remove()
  shutil.rmtree(SITE/'instance',ignore_errors=True)
 def setUp(self):self.client=self.app.test_client()
 def snap(self):
  c=sqlite3.connect(RUNTIME)
  try:
   ts=[r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")];return {t:c.execute(f'select * from "{t}" order by rowid').fetchall() for t in ts}
  finally:c.close()
 def login(self,next_url=None):
  route='/login'+(f'?next={next_url}' if next_url else '');p=self.client.get(route);return self.client.post(route,data={'csrf_token':csrf(p),'email':'alice@osu.edu','password':'test1234'},follow_redirects=False)
 def test_all_routes_render(self):
  paths=['/','/about','/academics','/programs','/programs?college=engineering','/research','/departments','/faculty','/news','/events','/athletics','/admissions','/search?q=cancer+research','/login','/register','/_health']
  with self.app.app_context():
   paths += [f'/programs/{x.slug}' for x in self.module.Program.query.all()];paths += [f'/research/{x.slug}' for x in self.module.ResearchCenter.query.all()];paths += [f'/departments/{x.slug}' for x in self.module.Department.query.all()];paths += [f'/faculty/{x.slug}' for x in self.module.Faculty.query.all()];paths += [f'/news/{x.slug}' for x in self.module.NewsArticle.query.all()];paths += [f'/events/{x.id}' for x in self.module.Event.query.all()];paths += [f'/athletics/{x.slug}' for x in self.module.AthleticTeam.query.all()]
  for path in paths:
   with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,200)
 def test_real_image_assets_are_served(self):
  import json
  for item in json.loads((SITE/'image_sources.json').read_text())['images']:
   with self.subTest(file=item['file']):
    response=self.client.get('/static/images/'+item['file']);self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'image/webp');self.assertGreater(len(response.get_data()),5000);response.close()
 def test_get_routes_are_read_only(self):
  before=self.snap()
  for p in ('/','/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy','/about','/search?q=cancer+research','/events'):self.assertEqual(self.client.get(p).status_code,200)
  self.assertEqual(before,self.snap())
 def test_logout_and_csrf(self):
  self.assertEqual(self.client.get('/logout').status_code,405)
  for p in ('/logout','/bookmark/add','/bookmark/remove'):
   with self.subTest(p=p):self.assertEqual(self.client.post(p).status_code,400)
 def test_open_redirect_rejected_and_login_works(self):
  r=self.login('//evil.invalid');self.assertEqual(r.status_code,302);self.assertEqual(r.headers['Location'],'/')
 def test_invalid_bookmarks_rejected(self):
  self.login();p=self.client.get('/programs/juris-doctor-jd');tok=csrf(p)
  self.assertEqual(self.client.post('/bookmark/add',data={'csrf_token':tok,'item_type':'invalid','item_id':'1'}).status_code,400)
  p=self.client.get('/programs/juris-doctor-jd');self.assertEqual(self.client.post('/bookmark/add',data={'csrf_token':csrf(p),'item_type':'program','item_id':'99999'}).status_code,404)
 def test_valid_bookmark_and_duplicate_are_single_row(self):
  self.login();p=self.client.get('/programs/juris-doctor-jd');data={'csrf_token':csrf(p),'item_type':'program','item_id':'14','next':'/programs/juris-doctor-jd'};self.assertEqual(self.client.post('/bookmark/add',data=data).status_code,302)
  p=self.client.get('/programs/juris-doctor-jd');data['csrf_token']=csrf(p);self.assertEqual(self.client.post('/bookmark/add',data=data).status_code,302)
  c=sqlite3.connect(RUNTIME);self.assertEqual(c.execute("select count(*) from bookmarks where user_id=1 and item_type='program' and item_id=14").fetchone()[0],1);c.close()
 def test_upcoming_events_visible_with_fixed_clock(self):
  body=self.client.get('/events').get_data(as_text=True);self.assertIn('Buckeyes vs. Michigan State Football',body);self.assertIn('CFAES Annual Farm Science Review',body)
 def test_request_size_limit(self):self.assertEqual(self.client.post('/register',data=b'x'*(65*1024),content_type='application/x-www-form-urlencoded').status_code,413)
if __name__=='__main__':unittest.main()
