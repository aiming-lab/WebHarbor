"""Behavioral regression tests for the PR 175 reviewer fixes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SITE_ROOT = Path(__file__).resolve().parents[1]
SITE = SITE_ROOT.name

class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / SITE
        shutil.copytree(SITE_ROOT, cls.root, ignore=shutil.ignore_patterns('instance', '__pycache__', 'images', 'external_cache'))
        (cls.root / 'instance').mkdir()
        cls.seed = cls.root / 'instance_seed' / (SITE + '.db')
        shutil.copy2(cls.seed, cls.root / 'instance' / (SITE + '.db'))
        sys.path.insert(0, str(cls.root))
        spec = importlib.util.spec_from_file_location('review_app_'+SITE, cls.root/'app.py')
        cls.mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = cls.mod; spec.loader.exec_module(cls.mod)
        cls.app = cls.mod.app; cls.app.config['TESTING'] = True
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context(): cls.mod.db.engine.dispose()
        sys.path.remove(str(cls.root)); cls.tmp.cleanup()
    def setUp(self):
        with self.app.app_context(): self.mod.db.session.remove(); self.mod.db.engine.dispose()
        shutil.copy2(self.seed,self.root/'instance'/(SITE+'.db'))
        self.client=self.app.test_client()
    def token(self):
        self.client.get('/')
        with self.client.session_transaction() as sess:
            # Get the signed token through the form, not the raw session secret.
            pass
        import re
        return re.search(r'name="csrf-token" content="([^"]+)"', self.client.get('/').get_data(as_text=True)).group(1)
    def post(self,url,data=None,json_data=None):
        token=self.token()
        return self.client.post(url,data={**(data or {}),'csrf_token':token}) if json_data is None else self.client.post(url,json=json_data,headers={'X-CSRFToken':token})
    def login(self,email='bob.c@test.com',next_url=None):
        return self.post('/login'+('?'+'next='+next_url if next_url else ''),{'email':email,'password':'TestPass123!'})
    def test_populated_startup_and_gets_are_byte_identical(self):
        dbfile=self.root/'instance'/(SITE+'.db');before=hashlib.sha256(dbfile.read_bytes()).hexdigest()
        for url in ['/', '/search?q=Camry', '/_health']:
            self.assertEqual(self.client.get(url).status_code,200)
        with self.app.app_context():
            self.mod.seed_database();self.mod.seed_benchmark_users()
        self.assertEqual(hashlib.sha256(dbfile.read_bytes()).hexdigest(),before)
    def test_redirect_rejects_external_and_backslash_targets(self):
        from urllib.parse import quote
        for target in ['//example.com','/\\example.com','https://example.com','/x\ny']:
            with self.subTest(target=target):
                self.client=self.app.test_client();r=self.login(next_url=quote(target,safe=''))
                self.assertEqual(r.status_code,302);self.assertEqual(r.location,'/')
    def test_login_preserves_local_destination(self):
        r=self.login(next_url='/account');self.assertEqual(r.location,'/account')
    def test_csrf_required(self):
        self.login()
        url={'healthgrades':'/doctor/dr-janet-chieh-yrxtb/save','kelley_blue_book':'/vehicle/toyota-camry-2026/save','uniqlo':'/cart/add/115'}[SITE]
        self.assertEqual(self.client.post(url).status_code,400)
    def test_cross_account_rows_are_protected(self):
        self.login()
        url={'healthgrades':'/account/appointments/2/cancel','kelley_blue_book':'/account/quotes/2/cancel','uniqlo':'/cart/remove/1'}[SITE]
        self.assertEqual(self.post(url).status_code,404)
    def test_review_preserves_upstream_aggregate(self):
        if SITE=='kelley_blue_book':self.skipTest('No user review route')
        self.login();model=self.mod.Doctor if SITE=='healthgrades' else self.mod.Product
        slug='dr-bryan-sires-xy9bc' if SITE=='healthgrades' else 'supima-cotton-t-shirt-e455365-000';kind='doctor' if SITE=='healthgrades' else 'product'
        with self.app.app_context():
            obj=model.query.filter_by(slug=slug).one();count=obj.review_count;rating=obj.rating;before=self.mod.Review.query.count()
        r=self.post('/'+kind+'/'+slug+'/review',{'rating':5,'title':'Good','body':'A useful review'})
        self.assertEqual(r.status_code,302)
        with self.app.app_context():
            obj=model.query.filter_by(slug=slug).one();self.assertEqual(obj.review_count,count+1);self.assertAlmostEqual(obj.rating,(rating*count+5)/(count+1));self.assertEqual(self.mod.Review.query.count(),before+1)
    def test_appointment_date_validated(self):
        if SITE!='healthgrades':self.skipTest('Healthgrades only')
        self.login();url='/doctor/dr-kevin-dooms-y2n6c/request-appointment'
        with self.app.app_context():n=self.mod.Appointment.query.count()
        for date in ['tomorrow','2026-02-30','']:
            self.post(url,{'patient_name':'Bob Chen','reason':'Consultation','preferred_date':date})
        with self.app.app_context():self.assertEqual(self.mod.Appointment.query.count(),n)
        self.post(url,{'patient_name':'Bob Chen','reason':'Consultation','preferred_date':'2026-11-18'})
        with self.app.app_context():self.assertEqual(self.mod.Appointment.query.count(),n+1)
    def test_comparison_accumulates_and_removes(self):
        if SITE!='kelley_blue_book':self.skipTest('KBB only')
        for slug in ['toyota-camry-2026','tesla-model-3-2026','toyota-camry-2026']:self.post('/compare/add/'+slug)
        r=self.client.get('/compare').get_data(as_text=True)
        self.assertIn('2026 Toyota Camry',r);self.assertIn('2026 Tesla Model 3',r)
        with self.client.session_transaction() as s:self.assertEqual(len(s['comparison']),2)
        self.post('/compare/remove/toyota-camry-2026')
        with self.client.session_transaction() as s:self.assertEqual(s['comparison'],['tesla-model-3-2026'])
    def test_quote_requires_actual_trim_and_zip(self):
        if SITE!='kelley_blue_book':self.skipTest('KBB only')
        self.login()
        with self.app.app_context():n=self.mod.QuoteRequest.query.count()
        for trim,zip_code in [('Invented','78701'),('LE','abc'),('LE',''),('LE','123456')]:self.post('/vehicle/toyota-camry-2026/quote',{'trim_name':trim,'zip_code':zip_code})
        with self.app.app_context():self.assertEqual(self.mod.QuoteRequest.query.count(),n)
        self.post('/vehicle/toyota-camry-2026/quote',{'trim_name':'LE','zip_code':'78701'})
        with self.app.app_context():self.assertEqual(self.mod.QuoteRequest.query.count(),n+1)
    def test_unknown_prices_and_spec_units(self):
        if SITE!='kelley_blue_book':self.skipTest('KBB only')
        r=self.client.get('/vehicle/bmw-4-series-2027').get_data(as_text=True);self.assertIn('Price unavailable',r);self.assertNotIn('Starting at $29',r)
        r=self.client.get('/vehicle/honda-odyssey-2026').get_data(as_text=True);self.assertIn('Cargo Volume',r);self.assertIn('Seating',r)
        with self.app.app_context():self.assertEqual(self.mod.VehicleTrim.query.filter(self.mod.VehicleTrim.price<1000).count(),0)
    def test_nested_categories_work(self):
        if SITE!='uniqlo':self.skipTest('UNIQLO only')
        self.assertEqual(self.client.get('/women/tops/t-shirts').status_code,200)
    def test_cart_quantities_and_stock(self):
        if SITE!='uniqlo':self.skipTest('UNIQLO only')
        self.login()
        for qty in ['0','-1','11','bad','1.2']:
            with self.subTest(qty=qty):self.assertEqual(self.post('/cart/add/115',{'quantity':qty}).status_code,400)
        self.assertEqual(self.post('/cart/add/115',{'quantity':'10'}).status_code,302)
        self.assertEqual(self.post('/cart/add/115',{'quantity':'1'}).status_code,400)
        with self.app.app_context():
            item=self.mod.CartItem.query.filter_by(user_id=2,variant_id=115).one();iid=item.id;self.assertEqual(item.quantity,10)
            item.variant.in_stock=False;self.mod.db.session.commit()
        self.assertEqual(self.post('/cart/add/115',{'quantity':'1'}).status_code,400)
        for qty in ['bad',-1,11,1.5,True]:self.assertEqual(self.post('/api/cart/update',json_data={'item_id':iid,'quantity':qty}).status_code,400)
        self.assertEqual(self.post('/api/cart/update',json_data={'item_id':iid,'quantity':0}).status_code,200)
    def test_variants_remain_distinguishable(self):
        if SITE!='uniqlo':self.skipTest('UNIQLO only')
        with self.app.app_context():
            rows=self.mod.ProductVariant.query.all();keys=[(r.product_id,r.color,r.size) for r in rows];self.assertEqual(len(keys),len(set(keys)))
    def test_migration_is_idempotent(self):
        p=self.root/'migrate_seed.py'
        if not p.exists():self.skipTest('No migration')
        spec=importlib.util.spec_from_file_location('migration_'+SITE,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        before=hashlib.sha256(self.seed.read_bytes()).hexdigest();m.migrate(self.seed);self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
