"""Behavioral self-checks for the Michaels mirror (contributor pre-PR tests).

Runs against a throwaway copy of the site with the shipped instance_seed DB.
"""
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
SITE = SITE_ROOT.name


class MichaelsMirrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / SITE
        shutil.copytree(SITE_ROOT, cls.root,
                        ignore=shutil.ignore_patterns('instance', '__pycache__', 'scraped_data'))
        (cls.root / 'instance').mkdir()
        cls.seed = cls.root / 'instance_seed' / (SITE + '.db')
        shutil.copy2(cls.seed, cls.root / 'instance' / (SITE + '.db'))
        sys.path.insert(0, str(cls.root))
        spec = importlib.util.spec_from_file_location('michaels_test_app', cls.root / 'app.py')
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.mod
        spec.loader.exec_module(cls.mod)
        cls.app = cls.mod.app
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.mod.db.engine.dispose()
        sys.path.remove(str(cls.root))
        cls.tmp.cleanup()

    def client(self):
        return self.app.test_client()

    # ---------------- health ----------------

    def test_health_ok(self):
        with self.client() as c:
            r = c.get('/_health')
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertTrue(data['ok'])
            self.assertGreaterEqual(data['counts']['products'], 300)
            self.assertGreaterEqual(data['counts']['reviews'], 250)
            self.assertGreaterEqual(data['counts']['stores'], 40)
            self.assertGreaterEqual(data['counts']['coupons'], 8)
            self.assertGreaterEqual(data['counts']['classes'], 30)

    # ---------------- catalog ----------------

    def test_homepage_renders_catalog(self):
        with self.client() as c:
            r = c.get('/')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            for nav in ['Halloween', 'Yarn &amp; Needlework', 'Frames', 'Canvas']:
                self.assertIn(nav, html)
            self.assertIn('Best Sellers', html)
            self.assertIn('GETMY30', html)

    def test_search_relevance(self):
        with self.client() as c:
            r = c.get('/search?q=National+Geographic+Metal+Detector+Starter+Kit')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertIn('National Geographic™ Metal Detector Starter Kit', html)

    def test_listing_filters(self):
        with self.client() as c:
            r = c.get('/shop/floral?availability=pickup&sort=price_low')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertIn('Dahlia', html)

    def test_pdp_variants_and_description(self):
        with self.client() as c:
            r = c.get('/product/level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertIn('archival', html.lower())
            self.assertIn('gesso', html.lower())
            self.assertIn('48&#34; x 48&#34;', html)
            self.assertIn('109.99', html)

    def test_reviews_page_shows_real_distribution(self):
        with self.client() as c:
            r = c.get('/product/level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532/reviews')
            self.assertEqual(r.status_code, 200)
            html = r.data.decode()
            self.assertIn('14630', html)   # real upstream 5-star count

    # ---------------- cart / promos ----------------

    def _login(self, c, email='alice.j@test.com', pw='TestPass123!'):
        r = c.post('/login', data={'email': email, 'password': pw})
        self.assertEqual(r.status_code, 302)

    def test_getmy30_discount_math(self):
        with self.client() as c:
            self._login(c)
            # compute the expected discount from the seeded cart itself
            CartItem = self.mod.CartItem
            with self.app.app_context():
                subtotal = sum(i.product.price_for(i.variant_sku) * i.qty
                               for i in CartItem.query.filter_by(user_id=1).all())
            expected = round(subtotal * 0.30, 2)
            r = c.post('/cart/coupon', data={'code': 'getmy30'})
            self.assertEqual(r.status_code, 302)
            r = c.get('/cart')
            html = r.data.decode()
            self.assertIn(f'{expected:.2f}', html)

    def test_instore_coupon_rejected_online(self):
        with self.client() as c:
            self._login(c)
            r = c.post('/cart/coupon', data={'code': 'SAVE30'})  # unknown code
            r = c.get('/cart')
            self.assertIn('not recognized', r.data.decode())

    def test_bogo_free_cart_math(self):
        with self.client() as c:
            self._login(c, 'david.k@test.com')
            c.post('/cart/add', data={'slug': '10-x-10-flat-white-deep-profile-shadow-box-by-studio-d-cor-10739210', 'qty': '1'})
            c.post('/cart/add', data={'slug': '11-x-14-classic-white-shadow-box-by-studio-d-cor-10739209', 'qty': '1'})
            r = c.get('/cart')
            html = r.data.decode()
            self.assertIn('Buy One Get One mix &amp; match', html)
            self.assertIn('17.49', html)   # cheaper of the pair is free

    def test_anonymous_pending_cart_adds_all_land_after_login(self):
        """S-1 regression: consecutive anonymous add-to-cart intents must all
        land in the cart after login (list merge, not single-slot overwrite).
        Cleans up its own cart rows so the suite stays order-independent."""
        CartItem = self.mod.CartItem
        slugs = ['national-geographic-metal-detector-starter-kit-10758215',
                 'snap-circuits-explorer-100-experiments-10567231']
        try:
            with self.client() as c:
                # anonymous: the same item twice, then a different item
                c.post('/cart/add', data={'slug': slugs[0], 'qty': '1'})
                c.post('/cart/add', data={'slug': slugs[0], 'qty': '1'})
                c.post('/cart/add', data={'slug': slugs[1], 'qty': '1'})
                self._login(c)
                r = c.get('/cart')
                html = r.data.decode()
                self.assertIn('Metal Detector', html)
                self.assertIn('Snap Circuits', html)
                with self.app.app_context():
                    rows = {(i.product.slug, i.variant_sku): i.qty
                            for i in CartItem.query.filter_by(user_id=1).all()}
                self.assertEqual(rows[(slugs[0], '')], 2)
                self.assertEqual(rows[(slugs[1], '')], 1)
        finally:
            with self.app.app_context():
                Product = self.mod.Product
                ids = [p.id for p in Product.query.filter(Product.slug.in_(slugs)).all()]
                CartItem.query.filter(CartItem.user_id == 1,
                                      CartItem.product_id.in_(ids)) \
                    .delete(synchronize_session=False)
                self.mod.db.session.commit()

    # ---------------- stores / classes / savings ----------------

    def test_store_locator(self):
        with self.client() as c:
            r = c.get('/store-locator?q=Cary')
            html = r.data.decode()
            self.assertIn('Crossroads Plaza', html)
            self.assertIn('balloon inflation', html)
            r = c.get('/store-locator?q=NC')
            self.assertEqual(r.data.decode().count('store-card'), 5)

    def test_classes_page_and_categories(self):
        with self.client() as c:
            r = c.get('/classes')
            html = r.data.decode()
            self.assertIn('Sew a Reversible Witch Hat', html)
            r = c.get('/classes?category=Fabric%20%26%20Sewing')
            html = r.data.decode()
            self.assertIn('tutorial-card', html)

    def test_savings_page(self):
        with self.client() as c:
            r = c.get('/savings')
            html = r.data.decode()
            self.assertIn('GETMY30', html)
            self.assertIn('In-Store Only', html)
            r = c.get('/coupon-policy-and-price-guarantee')
            self.assertIn('one coupon of each type per day', r.data.decode())

    # ---------------- account ----------------

    def test_order_history_math(self):
        with self.client() as c:
            self._login(c)
            r = c.get('/account/order/MI2609180101002')
            html = r.data.decode()
            self.assertIn('GETMY30', html)
            self.assertIn('22.90', html)   # 29.94 - 8.98 + 1.94

    # ---------------- tasks contract ----------------

    def test_tasks_jsonl_contract(self):
        rows = [json.loads(l) for l in (SITE_ROOT / 'tasks.jsonl').read_text().splitlines() if l.strip()]
        self.assertEqual(len(rows), 19)
        required = {'web_name', 'id', 'ques', 'web', 'upstream_url'}
        grading = {'verifier_path', 'judge_rubric'}  # appended by the review contract
        for row in rows:
            self.assertTrue(required <= set(row), f'missing keys {required - set(row)}')
            self.assertTrue(set(row) <= (required | grading), f'unexpected keys {set(row) - required - grading}')
            self.assertEqual(row['web'], 'http://localhost:40088/')
            self.assertLessEqual(len(row['ques'].split()), 100)
            self.assertNotIn('answer', row)

    # ---------------- seed idempotency (byte stability at boot) ----------------

    def test_boot_leaves_seed_bytes_untouched(self):
        db_path = self.root / 'instance' / (SITE + '.db')
        before = hashlib.md5(db_path.read_bytes()).hexdigest()
        with self.app.app_context():
            self.mod.seed_database()      # populated DB -> early return
            self.mod.seed_benchmark_users()
        after = hashlib.md5(db_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
