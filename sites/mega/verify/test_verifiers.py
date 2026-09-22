"""Focused application, seed and semantic-grading regression tests.

Run with unittest discover or directly. Browser-based grading controls live in
review evidence, separately from these isolated fixtures.
"""
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SITE/'verify'))
import answers
from grade import preserved


class AnswerTests(unittest.TestCase):
    def test_recovery_policy(self):
        for text in ['Do not share it with support or teammates.', 'Support and teammates.', 'Keep the key private; neither the help desk nor your colleagues should receive it.']:
            with self.subTest(text=text):self.assertTrue(answers.recovery(text))
        for text in ['You should share the recovery key with support and teammates.', 'Never share it with support; send it to teammates.', 'It is safe to share it with support and teammates.']:
            with self.subTest(text=text):self.assertFalse(answers.recovery(text))

    def test_highlight_alternatives(self):
        self.assertTrue(answers.highlights('Fast downloads and uploads; Mobile and desktop access.'))
        self.assertTrue(answers.highlights('Mobile and desktop access; File and folder links.'))
        self.assertFalse(answers.highlights('Mobile and desktop access is not available. File and folder links.'))

    def test_comparison(self):
        for t in ['Business Pro', 'Business Pro includes 5 users; Pro II has 1.', 'Business Pro includes more users than Pro II.']:
            self.assertTrue(answers.business_winner(t),t)
        for t in ['Pro II includes more users than Business Pro: Pro II has 5 and Business Pro has 1.', 'Business Pro has 1; Pro II has 5.', 'Business Pro is not the winner.']:
            self.assertFalse(answers.business_winner(t),t)

    def test_wrong_version_not_rescued_by_reference(self):
        self.assertFalse(answers.package_version('MEGA Pass Chrome extension has version 9.9.9. The reference number is 1.12.4.','1.12.4'))
        for t in ['MEGA Pass Chrome extension, version 1.12.4','MEGA Pass Chrome extension | 1.12.4','MEGA Pass Chrome extension. The version shown is 1.12.4.','MEGA Pass Chrome extension\nVersion\n1.12.4']:
            self.assertTrue(answers.package_version(t,'1.12.4'),t)

    def test_2fa_contradiction(self):
        for t in ['Old vendor FTP','Old vendor FTP has no 2FA.','Old vendor FTP does not have two-factor authentication enabled.']:
            self.assertTrue(answers.old_vendor(t),t)
        self.assertFalse(answers.old_vendor('Old vendor FTP has two-factor authentication enabled.'))

    def test_polarity_after_label(self):
        self.assertFalse(answers.positive('Team dashboard is not the administration surface.',r'\bteam dashboard\b'))
        self.assertTrue(answers.positive('Not File links; Team dashboard is the administration surface.',r'\bteam dashboard\b'))

    def test_disconnect_variants(self):
        for t in ['Disconnect the affected device before restoring files.', 'First, take the infected computer offline before restoring files.', 'The compromised machine should be isolated.']:
            self.assertTrue(answers.disconnect(t),t)
        for t in ['Disconnect the unaffected backup device and leave the affected device connected.', 'Do not disconnect the affected device.', 'Disconnect the affected device; keep the infected device online.']:
            self.assertFalse(answers.disconnect(t),t)

    def test_ticket_intent(self):
        self.assertTrue(answers.ticket_request('Please help me estimate S4 egress for quarterly archives.'))
        self.assertTrue(answers.ticket_request('How can I calculate outbound traffic for S4 archives every quarter?'))
        self.assertFalse(answers.ticket_request('S4 egress quarterly; I do not need help estimating archives; close my account.'))

    def test_no_unrelated_changes(self):
        b={'users':[{'id':1,'company':'A','name':'Alice'},{'id':2,'company':'B','name':'Bob'}]}
        a=json.loads(json.dumps(b));a['users'][0]['company']='Updated'
        self.assertTrue(preserved(b,a,{'users':{1:{'company'}}}))
        a['users'][1]['company']='Corrupted';self.assertFalse(preserved(b,a,{'users':{1:{'company'}}}))


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='mega-tests-');cls.root=Path(cls.temp.name)
        for f in ['app.py','seed_data.py','migrate_seed.py']:
            shutil.copy2(SITE/f,cls.root/f)
        shutil.copytree(SITE/'templates',cls.root/'templates')
        (cls.root/'instance').mkdir();(cls.root/'instance_seed').mkdir()
        cls.seed=cls.root/'instance_seed/mega.db'
        shutil.copy2(SITE/'instance_seed/mega.db',cls.seed)
        spec=importlib.util.spec_from_file_location('mega_migrate',cls.root/'migrate_seed.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cls.migrate=staticmethod(m.migrate);m.migrate(cls.seed)
        shutil.copy2(cls.seed,cls.root/'instance/mega.db');sys.path.insert(0,str(cls.root))
        import app
        cls.mod=app;app.app.config['TESTING']=True

    def setUp(self):
        with self.mod.app.app_context():self.mod.db.session.remove();self.mod.db.engine.dispose()
        shutil.copy2(self.seed,self.root/'instance/mega.db');self.client=self.mod.app.test_client()
        self.client.post('/login',data={'email':'alice.j@test.com','password':'TestPass123!'})

    def cart(self,slug='pro-i',cycle='monthly',seats=1):
        return self.client.post('/cart/add/'+slug,data={'billing_cycle':cycle,'seats':seats})

    def purchase(self,payment_id=1,cycle='monthly',seats=1):
        return self.client.post('/checkout',data={'billing_cycle':cycle,'seats':seats,'payment_id':payment_id,'action':'purchase'})

    def query(self,sql):
        with sqlite3.connect(self.root/'instance/mega.db') as c:return c.execute(sql).fetchall()

    def test_default_payment_recorded(self):
        self.cart();r=self.purchase();self.assertIn('/orders/',r.location)
        self.assertEqual(self.query('SELECT payment_id,billing_cycle,seats,total FROM subscription_orders ORDER BY id DESC LIMIT 1'),[(1,'monthly',1,11.76)])
        self.assertEqual(self.query('SELECT * FROM checkout_carts'),[])

    def test_invalid_or_foreign_card_no_purchase(self):
        for pid in [999999,3,0]:
            self.cart();self.purchase(pid);self.assertEqual(len(self.query('SELECT * FROM subscription_orders')),4)

    def test_changed_selection_requires_review(self):
        self.cart();self.purchase(cycle='yearly',seats=2)
        self.assertEqual(len(self.query('SELECT * FROM subscription_orders')),4)
        self.assertEqual(self.query('SELECT billing_cycle,seats FROM checkout_carts'),[('yearly',2)])
        self.assertIn(b'$235.38',self.client.get('/checkout').data)
        self.purchase(cycle='yearly',seats=2);self.assertEqual(self.query('SELECT total FROM subscription_orders ORDER BY id DESC LIMIT 1'),[(235.38,)])

    def test_update_does_not_purchase(self):
        self.cart();self.client.post('/checkout',data={'action':'update','billing_cycle':'yearly','seats':'1','payment_id':'1'})
        self.assertEqual(len(self.query('SELECT * FROM subscription_orders')),4)
        self.assertIn(b'$117.69',self.client.get('/checkout').data)

    def test_reject_unsupported_cycle(self):
        self.cart('vpn-monthly','yearly');self.assertEqual(self.query('SELECT * FROM checkout_carts'),[])
        self.cart('pro-i','garbage');self.assertEqual(self.query('SELECT * FROM checkout_carts'),[])

    def test_business_minimum_seats(self):
        self.cart('business-pro','monthly',1);self.assertEqual(self.query('SELECT * FROM checkout_carts'),[])
        self.cart('business-pro','monthly',5);self.assertEqual(self.query('SELECT seats FROM checkout_carts'),[(5,)])

    def test_cart_is_account_specific(self):
        self.cart();self.client.get('/logout');self.client.post('/login',data={'email':'bob.c@test.com','password':'TestPass123!'})
        self.assertEqual(self.client.get('/checkout').location,'/pricing')
        self.assertEqual(self.query('SELECT user_id FROM checkout_carts'),[(1,)])

    def test_cmd_filter_contains_installer(self):
        self.assertIn(b'MEGAcmdSetup64.exe',self.client.get('/downloads?product=CMD&platform=Windows').data)

    def test_clue_not_on_pricing(self):
        self.assertNotIn(b'S3-compatible',self.client.get('/pricing?category=objectstorage').data)
        self.assertIn(b'S3-compatible API',self.client.get('/plans/s4-fixed-storage').data)

    def test_seed_migration_repeat_is_byte_identical(self):
        before=self.seed.read_bytes();self.migrate(self.seed);self.assertEqual(self.seed.read_bytes(),before)

    def test_migration_reproducible(self):
        other=self.root/'copy.db';shutil.copy2(self.seed,other);self.migrate(other);self.assertEqual(other.read_bytes(),self.seed.read_bytes())

    def test_legacy_archive_migration_is_reproducible(self):
        legacy=self.root/'legacy.db';shutil.copy2(self.seed,legacy)
        with sqlite3.connect(legacy) as conn:
            conn.execute('DROP TABLE checkout_carts')
            conn.execute('ALTER TABLE subscription_orders DROP COLUMN payment_id')
            conn.execute("UPDATE downloads SET product='Desktop' WHERE package_name='MEGAcmdSetup64.exe'")
            conn.execute("UPDATE plans SET tagline='Predictable S3-compatible storage' WHERE slug='s4-fixed-storage'")
        a,b=self.root/'migrated-a.db',self.root/'migrated-b.db'
        shutil.copy2(legacy,a);shutil.copy2(legacy,b)
        self.migrate(a);self.migrate(b)
        self.assertEqual(a.read_bytes(),b.read_bytes())
        with sqlite3.connect(a) as conn:
            self.assertEqual(conn.execute("SELECT product FROM downloads WHERE package_name='MEGAcmdSetup64.exe'").fetchone()[0],'CMD')
            self.assertIn('payment_id',[r[1] for r in conn.execute('PRAGMA table_info(subscription_orders)')])
            self.assertEqual(conn.execute('SELECT count(*) FROM checkout_carts').fetchone()[0],0)

    def test_populated_startup_no_writes(self):
        before=(self.root/'instance/mega.db').read_bytes()
        with self.mod.app.app_context():
            self.mod.db.create_all();self.mod.seed_database();self.mod.seed_benchmark_users()
        self.assertEqual((self.root/'instance/mega.db').read_bytes(),before)

    def test_nonfinite_upload_size(self):
        self.client.post('/cloud/upload',data={'name':'probe.pdf','size_mb':'NaN','folder':'/'})
        size=self.query("SELECT size_mb FROM cloud_items WHERE name='probe.pdf'")[0][0]
        self.assertIsNotNone(size);self.assertGreaterEqual(size,0)

    @classmethod
    def tearDownClass(cls):
        with cls.mod.app.app_context():cls.mod.db.session.remove();cls.mod.db.engine.dispose()
        sys.path.remove(str(cls.root));cls.temp.cleanup()


if __name__=='__main__':unittest.main()
