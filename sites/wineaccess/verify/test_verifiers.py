import copy
import html
import importlib.util
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from answers import answer_ok
from verify_lib import evaluate

SITE = Path(__file__).resolve().parents[1]
ANSWERS = {
    0: 'Added one bottle to the cart.', 1: 'Saved the RAEN bottle.',
    2: 'Fantesca Estate Chardonnay has the later drinking window.',
    3: 'Chateau Haut-Brion, Pessac-Leognan, costs $950.',
    4: 'A suggested pairing is fried chicken.', 5: 'Saved.',
    6: 'The tracking number is 9400111899.', 7: 'Added two bottles.',
    8: 'Its drinking window is 2026 through 2031.',
    9: 'Bank Shot is cheaper: $39.60 per bottle, versus Le Pich at $57.20.',
    10: 'The Connoisseurs Club now appears in the account.',
    11: 'Order WA-260411-204: 4 bottles, total paid $324.75. 122 Camino Oruga, Building A, Napa, CA 94558. Phone: (866) 946-3923.',
    12: 'Maison Leroy Gevrey-Chambertin ends latest in 2035.',
    13: 'Created the account and reached checkout without placing an order.',
    14: 'Removed one line and checked the new total.',
    16: 'The new order number is WA-260520-1005.',
    15: 'Etna Bianco Carricante: roast chicken, shellfish, and spring vegetables.',
    17: 'Discovery costs $27.50 per bottle; Connoisseurs costs $75 per bottle. I recommend Discovery as cheaper. Members can delay shipping during heat or cold to protect wine. An adult signature is required at delivery.',
}


class WineAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        for name in ('app.py', 'seed_data.py'):
            shutil.copy2(SITE / name, cls.root / name)
        shutil.copytree(SITE / 'templates', cls.root / 'templates')
        (cls.root / 'instance').mkdir()
        cls.runtime = cls.root / 'instance/wineaccess.db'
        cls.seed = SITE / 'instance_seed/wineaccess.db'
        shutil.copy2(cls.seed, cls.runtime)
        sys.path.insert(0, str(cls.root))
        spec = importlib.util.spec_from_file_location('wineaccess_fixture', cls.root / 'app.py')
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.mod
        spec.loader.exec_module(cls.mod)
        cls.app = cls.mod.app
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.mod.db.session.remove()
            cls.mod.db.engine.dispose()
        sys.path.remove(str(cls.root))
        sys.modules.pop("wineaccess_fixture", None)
        cls.tmp.cleanup()

    def setUp(self):
        with self.app.app_context():
            self.mod.db.session.remove()
            self.mod.db.engine.dispose()
        shutil.copy2(self.seed, self.runtime)
        self.client = self.app.test_client()
        self.run = self.root / 'run'
        self.run.mkdir(exist_ok=True)
        shutil.copy2(self.seed, self.run / 'initial.db')
        self.steps = []

    def request(self, path, data=None):
        response = self.client.get(path, follow_redirects=True) if data is None else self.client.post(path, data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:100])
        text = html.unescape(re.sub('<[^>]+>', ' ', response.get_data(as_text=True)))
        self.steps.append({'url': 'http://localhost:40016' + response.request.path + ('?' + response.request.query_string.decode() if response.request.query_string else ''), 'page_text': text})
        return response

    def login(self, who='alice.j'):
        self.request('/login', {'email': who + '@test.com', 'password': 'TestPass123!'})

    def detail(self, fragment):
        with sqlite3.connect(self.runtime) as db:
            wid, slug = db.execute('SELECT id,slug FROM wines WHERE slug LIKE ?', ('%' + fragment + '%',)).fetchone()
        self.request('/wine/' + slug)
        return wid

    def positive(self, i):
        if i in {0, 1, 4, 5, 7, 16}: self.login()
        if i == 0:
            self.request('/store/?region=Napa&max_price=49.99');wid=self.detail('2023-karo-kann');self.request(f'/cart/add/{wid}', {'quantity': '1'})
        elif i == 1:
            self.request('/store/?q=Sonoma+Coast+Pinot+Noir');wid=self.detail('2024-raen');self.request(f'/saved/add/{wid}', {});self.request('/saved')
        elif i == 2:
            self.detail('2022-dumol');self.detail('2022-fantesca')
        elif i == 3:
            self.request('/store/?region=France&type=Red&sort=score');self.detail('2015-chateau-haut-brion')
        elif i == 4:
            self.request('/store/?type=Sparkling');wid=self.detail('m-brugnon');self.request(f'/cart/add/{wid}', {'quantity': '1'})
        elif i == 5:
            with sqlite3.connect(self.runtime) as db:
                db.row_factory=sqlite3.Row;u=dict(db.execute('SELECT * FROM users WHERE id=1').fetchone())
            self.request('/account', {**u, 'favorite_variety': 'Pinot Noir'})
        elif i == 6:
            self.login('bob.c');self.request('/orders')
        elif i == 7:
            self.request('/store/?type=White&region=France');wid=self.detail('2023-domaine-roland');self.request(f'/cart/add/{wid}', {'quantity': '2'})
        elif i == 8:
            self.request('/store/?q=Oakville');self.detail('2021-pas-de-cheval-cabernet-sauvignon-prelude-oakville')
        elif i == 9:
            self.detail('2021-le-pich');self.detail('2021-bank-shot')
        elif i == 10:
            self.login('carol.d');self.request('/club/');self.request('/club/connoisseurs/');self.request('/club/join/connoisseurs', {})
        elif i == 11:
            self.request('/contact-us/');self.login();self.request('/orders');self.request('/orders/WA-260411-204')
        elif i == 12:
            self.request('/store/?q=Burgundy+Pinot+Noir')
            for slug in ('2017-maison-leroy-nuits', '2017-maison-leroy-gevrey', '2021-domaine-du-clos-de-tart'): self.detail(slug)
        elif i == 13:
            self.request('/register');self.request('/register', {'display_name':'New Person','email':'new@example.com','password':'TestPass123!'});self.request('/store/?type=Red&max_price=29');wid=self.detail('2022-paso-robles-gsm');self.request(f'/cart/add/{wid}', {'quantity':'1'});self.request('/checkout')
        elif i == 14:
            self.login('david.k');self.request('/cart');self.request('/cart/remove/10', {})
        elif i == 15:
            self.request('/store/?region=Italy&max_price=39.99');self.detail('2024-etna-bianco')
        elif i == 16:
            self.request('/cart');self.request('/checkout');self.request('/checkout', {'address_line1':'122 Camino Oruga','city':'Napa','state':'CA','zip_code':'94558','card_last4':'4242'})
        elif i == 17:
            self.request('/where-we-ship/');self.request('/club/discovery/');self.request('/club/connoisseurs/')
        with sqlite3.connect(self.runtime) as a, sqlite3.connect(self.run/'after.db') as b:a.backup(b)
        self.traj={'task_id':f'Wine Access--{i}','start_url':'http://localhost:40016/','steps':self.steps,'final_answer':ANSWERS[i]}
        return self.verdict(i)

    def verdict(self, i):
        return evaluate(i,self.traj,self.run/'initial.db',self.run/'after.db')

    def mutate(self, sql):
        with sqlite3.connect(self.run/'after.db') as db:db.executescript(sql)

    def test_all_tasks_accept_real_route_and_state_fixtures(self):
        for i in range(18):
            with self.subTest(task=i):
                self.setUp();self.assertTrue(self.positive(i)['pass'], self.verdict(i))

    def test_global_shop_and_search_are_full_catalogue(self):
        r=self.request('/');self.assertIn('href="/store/"',r.get_data(as_text=True))
        r=self.request('/store/');self.assertIn('60 selections',r.get_data(as_text=True))
        r=self.request('/store/is_offer/true/');self.assertIn('20 selections',r.get_data(as_text=True))
        r=self.request('/store/?q=DuMOL');self.assertIn('2022 DuMOL',r.get_data(as_text=True))

    def test_empty_filters_are_not_discarded(self):
        r=self.request('/store/?q=Cabernet&type=Red&max_price=1');self.assertIn('0 selections',r.get_data(as_text=True))

    def test_distinct_emails_with_same_local_part_register(self):
        for email in ('same@example.com','same@another.example'):
            self.client=self.app.test_client();self.request('/register',{'email':email,'display_name':'Same Name','password':'TestPass123!'})
        with sqlite3.connect(self.runtime) as db:self.assertEqual(db.execute("SELECT count(distinct username) FROM users WHERE email LIKE 'same@%'").fetchone()[0],2)

    def test_extra_cart_quantity_rejected(self):
        self.assertTrue(self.positive(0)['pass']);self.mutate('UPDATE cart_items SET quantity=20 WHERE id=13');self.assertFalse(self.verdict(0)['pass'])

    def test_preference_preserves_all_other_rows(self):
        self.assertTrue(self.positive(5)['pass']);self.mutate('DELETE FROM cart_items WHERE user_id=2');self.assertEqual(self.verdict(5)['reason'],'unexpected_database_changes')

    def test_removal_requires_deleted_line(self):
        self.assertTrue(self.positive(14)['pass']);shutil.copy2(self.run/'initial.db',self.run/'after.db');self.mutate('UPDATE cart_items SET quantity=1 WHERE id=10');self.assertFalse(self.verdict(14)['pass'])

    def test_membership_must_be_active(self):
        self.assertTrue(self.positive(10)['pass']);self.mutate("UPDATE club_memberships SET status='Cancelled' WHERE user_id=3 AND club_id=(SELECT id FROM clubs WHERE slug='connoisseurs')");self.assertFalse(self.verdict(10)['pass'])

    def test_checkout_exact_items_totals_owner_status_and_preservation(self):
        for sql in ("DELETE FROM order_items WHERE order_id=5", "UPDATE order_items SET quantity=99 WHERE order_id=5", "UPDATE orders SET total=1 WHERE id=5", "UPDATE orders SET user_id=2 WHERE id=5", "UPDATE orders SET status='Cancelled' WHERE id=5", "DELETE FROM orders WHERE id=2", "DELETE FROM cart_items WHERE user_id=2", "UPDATE wines SET inventory=0 WHERE id=60"):
            with self.subTest(sql=sql):
                self.setUp();self.assertTrue(self.positive(16)['pass']);self.mutate(sql);self.assertFalse(self.verdict(16)['pass'])

    def test_unspecified_cart_quantities_allow_positive_additions(self):
        for i in (4, 13):
            with self.subTest(task=i):
                self.setUp();self.assertTrue(self.positive(i)['pass'])
                self.mutate('UPDATE cart_items SET quantity=3 WHERE id=13')
                self.assertTrue(self.verdict(i)['pass'], self.verdict(i))

    def test_removal_rejects_incorrect_reported_total(self):
        self.assertTrue(self.positive(14)['pass'])
        self.traj['final_answer'] = 'Removed one item; the new total is $1.'
        self.assertFalse(self.verdict(14)['pass'])

    def test_checkout_requires_actual_number(self):
        self.assertTrue(self.positive(16)['pass']);self.traj['final_answer']='The order number is unavailable.';self.assertFalse(self.verdict(16)['pass'])

    def test_reads_cannot_modify_state(self):
        self.assertTrue(self.positive(17)['pass']);self.mutate('DELETE FROM cart_items');self.assertFalse(self.verdict(17)['pass'])

    def test_navigation_rejects_foreign_origin_and_query_substrings(self):
        self.assertTrue(self.positive(11)['pass'])
        for url in ('https://unrelated.invalid/contact-us/', 'http://localhost:40016/?next=/contact-us/'):
            self.traj['steps'][0]['url']=url;self.assertEqual(self.verdict(11)['reason'],'required_observed_navigation')

    def test_urls_without_observed_content_fail(self):
        self.assertTrue(self.positive(17)['pass']);self.traj['steps'][0].pop('page_text');self.assertFalse(self.verdict(17)['pass'])

    def test_bob_tracking_requires_bobs_observed_order(self):
        self.assertTrue(self.positive(6)['pass'])
        self.traj['steps']=[s for s in self.steps if '/orders' in s['url']]
        self.traj['steps'][0]['page_text']='Alice Order History WA-260412-105 9400111899';self.assertFalse(self.verdict(6)['pass'])

    def test_archive_wrapper_ignores_runtime_reset(self):
        self.assertTrue(self.positive(5)['pass']);(self.run/'trajectory.json').write_text(json.dumps(self.traj))
        command=[sys.executable,str(SITE/'verify/verify_5.py'),'--run_dir',str(self.run)]
        one=subprocess.run(command,capture_output=True,text=True);self.assertEqual(one.returncode,0,one.stdout)
        with self.app.app_context():self.mod.db.session.remove();self.mod.db.engine.dispose()
        shutil.copy2(self.seed,self.runtime)
        two=subprocess.run(command,capture_output=True,text=True);self.assertEqual(one.stdout,two.stdout)
        (self.run/'after.db').unlink();missing=subprocess.run(command,capture_output=True,text=True);self.assertEqual(missing.returncode,1)

    def test_correct_natural_answers(self):
        examples={2:['Fantesca.','Fantesca, not DuMOL, has the later window.','Fantesca Estate Chardonnay ends in 2037; DuMOL Chloe ends in 2034.'],3:['Chateau Haut-Brion, Pessac-Leognan. Price: 950 dollars.', 'Pessac-Leognan; current price is $950.'],7:['Added two bottles.','Done.'],9:['Bank Shot has the lower case price per bottle.','Bank Shot: $39.60 per bottle; Le Pich: $57.20 per bottle.'],12:['Gevrey-Chambertin has the latest end year: 2035.'],15:['Etna Bianco: roasted chicken, shellfish and spring veg.', 'Roast chicken, shellfish and spring vegetables.'],17:[ANSWERS[17], ANSWERS[17].replace('Members can delay shipping during heat or cold to protect wine.', 'They hold shipments in extreme temperatures to keep wine safe.'), ANSWERS[17].replace('Members can delay shipping during heat or cold to protect wine.', 'They do not ship during extreme heat to protect the wine.')]}
        for i,values in examples.items():
            for value in values:
                with self.subTest(task=i,answer=value):self.assertTrue(answer_ok(i,value))

    def test_targeted_wrong_answers(self):
        examples={2:['Fantesca starts in 2026 and ends in 2037, but DuMOL ends in 2040 and is later.','Fantesca has the earlier drinking window.'],3:['Chateau Haut-Brion Pessac-Leognan costs $9.50; reference 950.'],6:['The tracking number is not 9400111899; it is 1234567890.'],9:['Bank Shot is $57.20 and Le Pich is $39.60, so Le Pich is lower.','Bank Shot is more expensive: $39.60 versus Le Pich $57.20.'],12:['Gevrey-Chambertin does not end latest in 2035.'],17:['During heat or cold events, members cannot delay shipping to protect bottle condition.','They ship immediately during extreme heat to protect wine quality.']}
        for i,values in examples.items():
            for value in values:
                with self.subTest(task=i,answer=value):self.assertFalse(answer_ok(i,value))


    def test_revised_tasks_reject_old_short_completion(self):
        for i, old in ((11, '122 Camino Oruga, Building A, Napa, CA 94558. Phone: (866) 946-3923.'), (17, 'Members can delay shipping in heat or cold to protect wine.')):
            with self.subTest(task=i):
                self.setUp();self.assertTrue(self.positive(i)['pass'])
                self.traj['final_answer'] = old
                self.assertEqual(self.verdict(i)['reason'], 'answer_not_supported')

    def test_support_brief_uses_order_quantity_sum_and_identity(self):
        self.assertTrue(self.positive(11)['pass'])
        for old, new in (('4 bottles', '3 bottles'), ('4 bottles', 'not 4 bottles'), ('$324.75', '$300'), ('WA-260411-204', 'WA-260412-205'), ('total paid $324.75', 'total paid $1; reference $324.75')):
            with self.subTest(change=new):
                self.traj['final_answer'] = ANSWERS[11].replace(old, new)
                self.assertEqual(self.verdict(11)['reason'], 'answer_not_supported')
        self.traj['final_answer'] = ANSWERS[11].replace('4 bottles', 'four bottles').replace('total paid $324.75', 'total: 324.75 dollars')
        self.assertTrue(self.verdict(11)['pass'])

    def test_support_brief_requires_account_and_order_detail(self):
        self.assertTrue(self.positive(11)['pass'])
        for path in ('/account', '/orders/WA-260411-204', '/contact-us'):
            self.traj['steps'] = [s for s in self.steps if path not in s['url']]
            self.assertEqual(self.verdict(11)['reason'], 'required_observed_navigation')
        self.traj['steps'] = self.steps
        self.traj['steps'][1]['page_text'] = 'Bob bob.c@test.com'
        self.assertEqual(self.verdict(11)['reason'], 'required_observed_navigation')

    def test_club_costs_units_direction_and_delivery_policy(self):
        good = ANSWERS[17]
        for old, new in (('$27.50', '$75'), ('$75', '$27.50'), ('per bottle', 'per shipment'), ('recommend Discovery as cheaper', 'recommend Connoisseurs as cheaper'), ('recommend Discovery as cheaper', 'think Connoisseurs is cheaper than Discovery'), ('can delay', 'cannot delay'), ('An adult signature is required', 'An adult signature is optional'), ('An adult signature is required', 'No adult signature is required')):
            with self.subTest(change=new):
                self.assertFalse(answer_ok(17, good.replace(old, new)))
        self.assertTrue(answer_ok(17, good.replace('Discovery costs $27.50 per bottle; Connoisseurs costs $75 per bottle.', 'Discovery: 110 dollars for 4 bottles, or 27.50 dollars per bottle. Connoisseurs: 150 dollars for 2 bottles, or 75 dollars per bottle.')))
        self.assertTrue(answer_ok(17, good.replace('Discovery costs $27.50 per bottle; Connoisseurs costs $75 per bottle.', 'Discovery per bottle: $27.50; Connoisseurs per bottle: $75.')))

    def test_club_planning_requires_both_details_and_shipping(self):
        self.assertTrue(self.positive(17)['pass'])
        for path in ('/club/discovery', '/club/connoisseurs', '/where-we-ship'):
            self.traj['steps'] = [s for s in self.steps if path not in s['url']]
            self.assertEqual(self.verdict(17)['reason'], 'required_observed_navigation')

if __name__=='__main__':unittest.main()
