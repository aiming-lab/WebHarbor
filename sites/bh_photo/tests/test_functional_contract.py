"""Regression tests for the closed B&H Photo functional findings.

Run with ``python -m unittest discover -s sites/bh_photo/tests -v``.
When running this file from elsewhere, set BH_PHOTO_SOURCE to the site
directory. Source files are copied into a TemporaryDirectory before import;
no source, runtime, or seed database is opened or modified.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path


class SiteFixture(unittest.TestCase):
    """Boots the real app against a throwaway SQLite DB with a tiny catalog."""

    @classmethod
    def setUpClass(cls):
        source_override = os.environ.get('BH_PHOTO_SOURCE')
        source = Path(source_override) if source_override else Path(__file__).resolve().parents[1]
        if not (source / 'app.py').is_file():
            raise RuntimeError('Set BH_PHOTO_SOURCE to the B&H Photo site directory')
        cls.scratch = tempfile.TemporaryDirectory(prefix='bh-photo-contract-')
        cls.addClassCleanup(cls.scratch.cleanup)
        fixture = Path(cls.scratch.name)
        shutil.copy2(source / 'app.py', fixture / 'app.py')
        shutil.copytree(source / 'templates', fixture / 'templates')
        shutil.copytree(source / 'static', fixture / 'static')

        # The only stub is the seed loader: the real app creates its normal
        # schema in the scratch directory and every request uses real routes.
        seed_stub = types.ModuleType('seed_data')
        seed_stub.seed_database = lambda *args, **kwargs: None
        seed_stub.seed_benchmark_users = lambda *args, **kwargs: None
        module_name = '_bh_photo_functional_fixture'
        spec = importlib.util.spec_from_file_location(module_name, fixture / 'app.py')
        cls.site = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = cls.site
        cls.addClassCleanup(sys.modules.pop, module_name, None)
        previous_seed_module = sys.modules.get('seed_data')
        sys.modules['seed_data'] = seed_stub
        try:
            spec.loader.exec_module(cls.site)
        finally:
            if previous_seed_module is None:
                sys.modules.pop('seed_data', None)
            else:
                sys.modules['seed_data'] = previous_seed_module

        cls.app = cls.site.app
        cls.app.config['TESTING'] = True
        cls.db = cls.site.db
        with cls.app.app_context():
            cls._seed_minimal_catalog()

    @classmethod
    def _seed_minimal_catalog(cls):
        s, db = cls.site, cls.db
        department = s.Category(name='Photography', slug='photography', nav_order=1)
        category = s.Category(
            name='Mirrorless Cameras', slug='mirrorless-cameras', nav_order=1,
            parent=department,
        )
        brand = s.Brand(name='Testbrand', slug='testbrand')
        db.session.add_all([department, category, brand])
        db.session.flush()
        store = s.StoreLocation(
            name='Test Pickup Counter', slug='test-pickup-counter', city='New York',
            state='NY', address='1 Test Plaza', pickup_hours='9-5',
        )
        product = s.Product(
            category_id=category.id, brand_id=brand.id, name='Test Camera',
            slug='test-camera', sku='BHTEST1', price=100.0, condition='New',
            availability='In Stock', stock_level=5, top_category_slug='photography',
            subcategory_slug='mirrorless-cameras', product_type='Mirrorless Camera',
        )
        user = s.User(email='tester@test.com', username='tester', display_name='Tester')
        user.set_password('TestPass123!')
        db.session.add_all([store, product, user])
        db.session.flush()
        db.session.add(s.Address(
            user_id=user.id, label='Studio', recipient='Tester', line1='1 Test Plaza',
            city='New York', state='NY', zip_code='10001', is_default=True,
        ))
        spec_group = s.ProductSpecGroup(
            product_id=product.id, title='Specifications', sort_order=0,
        )
        db.session.add(spec_group)
        db.session.flush()
        db.session.add_all([
            s.ProductSpec(group_id=spec_group.id, name='Lens Mount', value='Test Mount', sort_order=0),
            s.ProductSpec(group_id=spec_group.id, name='Angle of View', value='220°', sort_order=1),
        ])
        bundle = s.Bundle(
            title='Test Cinema Kit', slug='test-cinema-kit',
            description='A complete production package.', image_path=product.main_image,
            bundle_price=999.0, list_price=1099.0, audience='Cinema', featured=True,
        )
        db.session.add(bundle)
        db.session.flush()
        db.session.add(s.BundleItem(bundle_id=bundle.id, product_id=product.id, quantity=1))
        db.session.add(s.StoreInventory(
            store_id=store.id, product_id=product.id, quantity=3, pickup_eta='Ready in 2 hours',
        ))
        db.session.commit()
        cls.product_slug, cls.store_id, cls.user_email = product.slug, store.id, user.email

    def signed_in_client(self):
        client = self.app.test_client()
        response = client.post(
            '/login',
            data={'email': self.user_email, 'password': 'TestPass123!'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302, 'benchmark sign-in must succeed')
        return client

    def cart_rows(self):
        with self.app.app_context():
            return self.site.CartItem.query.count()

    def reservation_rows(self):
        with self.app.app_context():
            return self.site.StoreReservation.query.count()

    def order_rows(self):
        with self.app.app_context():
            return self.site.Order.query.count()


class MalformedNumericInputTests(SiteFixture):
    """Malformed numbers must produce a visible error, never an HTTP 500.

    Closes the two unhandled ``int()`` conversions found at S1 on the
    original contribution (app.py add_to_cart / update_cart / reserve).
    """

    def test_cart_add_rejects_non_numeric_quantity(self):
        client = self.signed_in_client()
        before = self.cart_rows()
        response = client.post(
            f'/cart/add/{self.product_slug}', data={'quantity': 'abc'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('valid quantity', response.get_data(as_text=True).lower())
        self.assertEqual(self.cart_rows(), before, 'rejected input must not write a cart row')

    def test_cart_add_accepts_valid_quantity(self):
        client = self.signed_in_client()
        before = self.cart_rows()
        response = client.post(
            f'/cart/add/{self.product_slug}', data={'quantity': '2'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cart_rows(), before + 1)

    def test_cart_update_rejects_non_numeric_quantity(self):
        client = self.signed_in_client()
        client.post(f'/cart/add/{self.product_slug}', data={'quantity': '1'})
        with self.app.app_context():
            item = self.site.CartItem.query.order_by(self.site.CartItem.id.desc()).first()
            item_id, before_quantity = item.id, item.quantity
        response = client.post(
            f'/cart/update/{item_id}', data={'quantity': 'abc'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('valid quantity', response.get_data(as_text=True).lower())
        with self.app.app_context():
            self.assertEqual(
                self.site.CartItem.query.get(item_id).quantity, before_quantity,
                'rejected input must not change the stored quantity',
            )

    def test_reserve_rejects_non_numeric_store(self):
        client = self.signed_in_client()
        before = self.reservation_rows()
        response = client.post(
            f'/reserve/{self.product_slug}',
            data={'store_id': 'abc', 'quantity': '1'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('pickup store', response.get_data(as_text=True).lower())
        self.assertEqual(self.reservation_rows(), before, 'rejected input must not reserve')

    def test_reserve_rejects_non_numeric_quantity(self):
        client = self.signed_in_client()
        before = self.reservation_rows()
        response = client.post(
            f'/reserve/{self.product_slug}',
            data={'store_id': str(self.store_id), 'quantity': 'abc'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('valid quantity', response.get_data(as_text=True).lower())
        self.assertEqual(self.reservation_rows(), before, 'rejected input must not reserve')

    def test_reserve_accepts_valid_input(self):
        client = self.signed_in_client()
        before = self.reservation_rows()
        response = client.post(
            f'/reserve/{self.product_slug}',
            data={'store_id': str(self.store_id), 'quantity': '1'}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.reservation_rows(), before + 1)


class StaticAssetTests(SiteFixture):
    def test_favicon_is_served(self):
        """Every page requested /favicon.ico and got a 404 at S1."""
        response = self.app.test_client().get('/favicon.ico')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.get_data()), 0)


class ShoppingPathTests(SiteFixture):
    def test_search_matches_plural_words_and_requires_all_terms(self):
        client = self.app.test_client()
        results = client.get('/search?q=test+cameras').get_data(as_text=True)
        unrelated = client.get('/search?q=unrelated+cameras').get_data(as_text=True)
        self.assertIn('href="/product/test-camera"', results)
        self.assertNotIn('href="/product/test-camera"', unrelated)

    def test_department_is_a_landing_page_before_the_listing(self):
        client = self.app.test_client()

        landing = client.get('/c/photography').get_data(as_text=True)
        listing = client.get('/c/mirrorless-cameras').get_data(as_text=True)

        self.assertIn('Shop Photography', landing)
        self.assertIn('Mirrorless Cameras', landing)
        self.assertIn('department-photo-hero', landing)
        self.assertIn('Video Chat</strong> with a Photography Expert', landing)
        self.assertIn('Photography Bags &amp; Cases', landing)
        self.assertGreaterEqual(
            landing.count('<img'), 20,
            'the department landing must retain the image-led density of the source page',
        )
        self.assertNotIn('class="filters"', landing)
        self.assertIn('class="filters"', listing)

    def test_listing_does_not_leak_detail_only_specifications(self):
        client = self.app.test_client()

        listing = client.get('/c/mirrorless-cameras').get_data(as_text=True)
        specs = client.get('/product/test-camera/specs').get_data(as_text=True)

        self.assertNotIn('Angle of View: 220', listing)
        self.assertIn('Angle of View', specs)
        self.assertIn('220°', specs)

    def test_bundle_search_leads_to_a_dedicated_detail_page(self):
        client = self.app.test_client()

        results = client.get('/bundles?q=Test+Camera').get_data(as_text=True)
        detail = client.get('/bundle/test-cinema-kit').get_data(as_text=True)

        self.assertIn('/bundle/test-cinema-kit', results)
        self.assertNotIn('href="/product/test-camera"', results)
        self.assertIn('Test Cinema Kit', detail)
        self.assertIn('Test Camera', detail)

    def test_checkout_requires_shipping_payment_and_review_steps(self):
        client = self.signed_in_client()
        client.post(f'/cart/add/{self.product_slug}', data={'quantity': '1'})
        before = self.order_rows()

        response = client.post(
            '/checkout',
            data={'step': 'shipping', 'fulfillment': 'Ship to address', 'address_id': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/checkout?step=payment'))
        self.assertEqual(self.order_rows(), before)

        response = client.post(
            '/checkout', data={'step': 'payment', 'payment_label': 'Demo Visa ending in 4242'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/checkout?step=review'))
        self.assertEqual(self.order_rows(), before)

        response = client.post(
            '/checkout',
            data={'step': 'review', 'note': 'Test order', 'confirmed': 'yes'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/order/BH-', response.location)
        self.assertEqual(self.order_rows(), before + 1)
        self.assertEqual(self.cart_rows(), 0)

    def test_checkout_cannot_skip_directly_to_review(self):
        client = self.signed_in_client()
        client.post(f'/cart/add/{self.product_slug}', data={'quantity': '1'})
        before = self.order_rows()

        response = client.post('/checkout', data={'step': 'review'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/checkout'))
        self.assertEqual(self.order_rows(), before)

    def test_checkout_requires_explicit_review_confirmation(self):
        client = self.signed_in_client()
        client.post(f'/cart/add/{self.product_slug}', data={'quantity': '1'})
        before = self.order_rows()
        client.post(
            '/checkout',
            data={'step': 'shipping', 'fulfillment': 'Ship to address', 'address_id': '1'},
        )
        client.post(
            '/checkout', data={'step': 'payment', 'payment_label': 'Demo Visa ending in 4242'},
        )

        response = client.post('/checkout', data={'step': 'review'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/checkout?step=review'))
        self.assertEqual(self.order_rows(), before)


if __name__ == '__main__':
    unittest.main()
