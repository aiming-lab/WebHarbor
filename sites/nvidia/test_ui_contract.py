#!/usr/bin/env python3
"""Mechanical UI contract tests. Import only an independent source copy.

Run with the site's existing Python and --output NEW_PRIVATE_DIRECTORY.
No browser, network, Docker, tasks, verifier, or source-tree runtime writes.
"""
import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import importlib
import io
import json
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import unittest
from urllib.parse import urlsplit

sys.dont_write_bytecode = True


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.words = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.words.append(data)

    @property
    def text(self):
        return ' '.join(' '.join(self.words).split())

    def attrs(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(source):
    files = [source / name for name in ('app.py', 'seed_data.py', 'test_ui_contract.py')]
    # The reviewer's private working note is not part of the shipped tree; hash it only
    # when it is present so this suite runs on a clean checkout (repair002, H1).
    notes = source / 'UI_REVIEW_NOTES.md'
    if notes.is_file():
        files.append(notes)
    for folder in ('templates', 'static/css', 'static/js', 'static/icons'):
        files.extend(p for p in (source / folder).rglob('*') if p.is_file())
    return sorted(files)


class UIContract(unittest.TestCase):
    def setUp(self):
        with module.app.app_context():
            module.db.session.remove()
            module.db.engine.dispose()
        shutil.copyfile(seed, database)
        self.client = module.app.test_client()

    def snapshot(self):
        with sqlite3.connect(database) as conn:
            tables = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: sorted(conn.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
                    for name in tables}

    def get(self, path, expected=200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected, path)
        page = response.get_data(as_text=True)
        key = hashlib.sha256((self.id() + path).encode()).hexdigest()[:16]
        (output / 'html' / f'{key}.html').write_text(page)
        routes.append({'test': self.id(), 'method': 'GET', 'path': path,
                       'status': response.status_code, 'html': f'html/{key}.html'})
        return page

    def token(self, path='/'):
        for field in Markup(self.get(path)).attrs('input'):
            if field.get('name') == 'csrf_token':
                return field['value']
        self.fail('CSRF token missing')

    def post(self, path, data=None, token=True, **kwargs):
        data = dict(data or {})
        if token:
            data['csrf_token'] = self.token()
        response = self.client.post(path, data=data, **kwargs)
        routes.append({'test': self.id(), 'method': 'POST', 'path': path,
                       'status': response.status_code, 'location': response.location})
        return response

    def login(self, email='alice.j@test.com', query=''):
        response = self.post('/login' + query, {'email': email, 'password': 'TestPass123!'})
        self.assertEqual(response.status_code, 302)
        return response

    def test_01_series_and_buying_pages(self):
        before = self.snapshot()
        for generation, architecture, tensor, rt in (
                ('50', 'Blackwell', 'Fifth-Gen Tensor Cores', 'Fourth-Gen RT Cores'),
                ('40', 'Ada Lovelace', 'Fourth-Gen Tensor Cores', 'Third-Gen RT Cores')):
            text = Markup(self.get(f'/geforce/graphics-cards/{generation}-series/')).text
            for fact in (architecture, tensor, rt, 'Technologies', 'Models',
                         'game', 'September 10, 2026', 'Buying Options'):
                self.assertIn(fact, text)
        page = Markup(self.get('/where-to-buy/geforce-rtx-5080'))
        for fact in ('NVIDIA Marketplace', 'United States / en-us', 'RTX 5080',
                     'Local Saved Selection', 'External References'):
            self.assertIn(fact, page.text)
        marketplace = [a['href'] for a in page.attrs('a')
                       if a.get('href', '').startswith('https://marketplace.nvidia.com/')]
        self.assertEqual(len(marketplace), 1)
        if references:
            raw = unescape((references / 'geforce-50/response.body').read_text())
            self.assertIn(marketplace[0], raw)
            self.assertIn('Fifth-Gen Tensor Cores', raw)
            ada = (references / 'ada-architecture/response.body').read_text()
            self.assertIn('Fourth-Gen Tensor Cores', ada)
            self.assertIn('Third-Gen RT Cores', ada)
            pro = unescape((references / 'pro-6000/response.body').read_text())
            self.assertIn('https://www.nvidia.com/en-us/contact/sales/', pro)
        self.get('/geforce/graphics-cards/30-series/', 404)
        self.get('/where-to-buy/not-a-product', 404)
        self.assertEqual(self.snapshot(), before)

    def test_02_all_read_routes_and_contact(self):
        paths = ['/', '/products', '/products?sort=price-low', '/where-to-buy',
                 '/compare', '/drivers', '/news', '/search?q=5080', '/login', '/register']
        with module.app.app_context():
            for p in module.Product.query.all():
                paths.extend([f'/products/{p.slug}', f'/where-to-buy/{p.slug}'])
            paths.extend(f'/news/{a.slug}' for a in module.Article.query.all())
            paths.extend(f'/drivers/{d.id}' for d in module.Driver.query.all())
        before = self.snapshot()
        for path in paths:
            page = self.get(path)
            self.assertNotIn('Add to Cart', page)
            self.assertNotIn('Place Order', page)
            self.assertNotIn('In Stock', page)
        contact = Markup(self.get('/where-to-buy/h200-tensor-core'))
        self.assertIn('required memory', contact.text)
        self.assertIn('general sales contact', contact.text)
        self.assertIn('https://www.nvidia.com/en-us/contact/sales/',
                      [a.get('href') for a in contact.attrs('a')])
        detail = Markup(self.get('/products/h200-tensor-core'))
        self.assertIn('/where-to-buy/h200-tensor-core', [a.get('href') for a in detail.attrs('a')])
        self.assertEqual(self.snapshot(), before)
        # Label all known contextual pictures at every active product-image surface.
        # Extended PR #107 fix round: the two family assets that share one vendor
        # artwork say so, the two official per-SKU 5080/5090 renders and the two
        # re-sourced official assets are labelled, and no surface describes one file
        # in two different ways.
        labels = {
            'geforce-rtx-4060': 'Official NVIDIA product render — RTX 4060 Ti (the RTX 4060 / RTX 4060 Ti family artwork)',
            'geforce-rtx-4070-super': 'Official NVIDIA product render — RTX 4070 SUPER',
            'geforce-rtx-4080-super': 'Official NVIDIA product render — RTX 4080 SUPER',
            'geforce-rtx-5060-ti': 'Official NVIDIA marketing image — RTX 5060 Ti',
            'geforce-rtx-5060': 'Official NVIDIA marketing image — RTX 5060 family desktop system',
            'geforce-rtx-5070-ti': 'Official NVIDIA product render — RTX 5070 Ti',
            'geforce-rtx-5070': 'Official NVIDIA product render — RTX 5070',
            'geforce-rtx-5080': 'Official NVIDIA product render — GeForce RTX 5080',
            'geforce-rtx-5090': 'Official NVIDIA product render — GeForce RTX 5090',
            'h100-tensor-core': 'Official NVIDIA product render — H100',
            'h200-tensor-core': 'Official NVIDIA product render — H200 Tensor Core GPU',
            'dgx-b200': 'Official NVIDIA product render — DGX B200',
            'l40s': 'Official NVIDIA product render — L40S',
            'rtx-pro-6000-blackwell': 'Official NVIDIA product render — RTX PRO 6000 Blackwell',
            'rtx-6000-ada': 'Official NVIDIA product render — RTX 6000 Ada Generation',
            'shield-tv-pro': 'Official NVIDIA product image — SHIELD TV Pro',
        }
        catalog = self.get('/products')
        comparison = self.get('/compare?ids=' + ','.join(labels))
        for slug, label in labels.items():
            with self.subTest(image_slug=slug):
                for html in (catalog, comparison, self.get('/products/' + slug)):
                    self.assert_image_label(html, slug, label)
        for route in ('/', '/search?q=5070', '/geforce/graphics-cards/50-series/'):
            self.assert_image_label(self.get(route), 'geforce-rtx-5070', labels['geforce-rtx-5070'])
        self.assert_image_label(self.get('/geforce/graphics-cards/50-series/'),
                                'geforce-rtx-5090', labels['geforce-rtx-5090'])
        self.assert_image_label(self.get('/geforce/graphics-cards/40-series/'),
                                'geforce-rtx-4080-super', labels['geforce-rtx-4080-super'])
        # The dedicated hero artwork is a different file from every product card, so no
        # page shows the same image twice (extended fix round).
        for route, hero in (('/', '/static/images/heroes/geforce-rtx-5090-hero.jpg'),
                            ('/geforce/graphics-cards/50-series/', '/static/images/heroes/geforce-rtx-50-series-hero.jpg'),
                            ('/geforce/graphics-cards/40-series/', '/static/images/heroes/geforce-rtx-40-series-hero.jpg')):
            html = self.get(route)
            images = Markup(html).attrs('img')
            sources = [image.get('src') for image in images]
            with self.subTest(hero=hero):
                self.assertIn(hero, sources)
                self.assertEqual(len(sources), len(set(sources)), route)
                self.assertIn('not a photograph of this model', html)
        # Every product image carries a caption (repair002, L6); slugs outside the
        # illustrations map get the generic wording.
        generic = {'rtx-4000-ada': 'RTX 4000 Ada Generation',
                   'rtx-5000-ada': 'RTX 5000 Ada Generation', 'jetson-orin-nx': 'Jetson Orin NX 16GB',
                   'jetson-orin-nano-super': 'Jetson Orin Nano Super Developer Kit',
                   'geforce-rtx-4090': 'GeForce RTX 4090',
                   'shield-tv': 'SHIELD TV'}
        for slug, name in generic.items():
            self.assert_image_label(catalog, slug, f'Local mirror illustration for {name}')
        self.login()
        self.assert_image_label(self.get('/account/wishlist'), 'geforce-rtx-4080-super',
                                labels['geforce-rtx-4080-super'])
        self.assertEqual(self.snapshot(), before)

    def assert_image_label(self, html, slug, label):
        start = html.index(f'data-product-image="{slug}"')
        figure = Markup(html[start:html.index('</figure>', start)])
        image = figure.attrs('img')[0]
        self.assertEqual(image['src'], f'/static/images/products/{slug}.png')
        self.assertTrue(label, slug)
        self.assertIn(label, image['alt'])
        self.assertIn('not a photograph of this model', image['alt'])
        self.assertIn(label + '; not a photograph of this model.', figure.text)
        self.assertEqual(len(figure.attrs('figcaption')), 1)

    def test_02b_integer_bounds_and_error_pages(self):
        """Out-of-range ids are 404, not 500; 500 renders the custom page (repair002, M3)."""
        self.get('/drivers/999999999999999999999', 404)
        self.get('/drivers/9223372036854775808', 404)
        self.get('/drivers/0', 404)
        self.login()
        self.get('/order/999999999999999999999', 404)
        self.get('/order/9223372036854775808', 404)
        self.assertEqual(self.post('/wishlist/add/999999999999999999999').status_code, 404)
        self.assertEqual(self.post('/wishlist/remove/999999999999999999999').status_code, 404)
        self.get('/order/1')
        self.assertIn(500, module.app.error_handler_spec[None])
        with module.app.test_request_context('/'):
            body, status = module.server_error(RuntimeError('probe'))
            self.assertEqual(status, 500)
            self.assertIn('Something Went Wrong', body)
        with module.app.app_context():
            self.assertIsNone(module.load_user(2 ** 63))
            self.assertIsNone(module.load_user('not-a-number'))

    def test_02c_request_body_limits(self):
        """Oversized bodies are 413 and oversized field values are not stored (repair002, M6)."""
        self.assertIn(413, module.app.error_handler_spec[None])
        before = self.snapshot()['newsletter']
        response = self.post('/newsletter', {'email': 'o' * 121 + '@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.snapshot()['newsletter'], before)
        response = self.post('/newsletter', {'email': 'b' * 2_000_000 + '@example.com'})
        self.assertEqual(response.status_code, 413)
        self.assertIn('Request Too Large', response.get_data(as_text=True))
        self.assertEqual(self.snapshot()['newsletter'], before)
        response = self.post('/newsletter', {'email': 'kept@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.snapshot()['newsletter']), len(before) + 1)

    def test_03_legacy_post_and_csrf_no_mutation(self):
        # A preexisting cart verifies update/remove/checkout cannot consume old rows.
        with module.app.app_context():
            module.db.session.add(module.CartItem(user_id=1, product_id=2, quantity=3))
            module.db.session.commit()
        before = self.snapshot()
        for authenticated in (False, True):
            if authenticated:
                self.login()
            for path in ('/cart', '/checkout'):
                response = self.client.get(path)
                self.assertEqual((response.status_code, response.location), (302, '/where-to-buy'))
            for path in ('/cart/add/2', '/cart/update/1', '/cart/remove/1', '/checkout'):
                self.assertEqual(self.post(path, token=False).status_code, 400)
                self.assertEqual(self.post(path, {'csrf_token': 'invalid'}, token=False).status_code, 400)
                response = self.post(path, {'quantity': 4, 'full_name': 'Demo', 'card': '0000000000000000'})
                self.assertEqual(response.status_code, 410)
                self.assertIn('no longer available', response.get_data(as_text=True))
                self.assertEqual(self.snapshot(), before)

    def test_04_wishlist_delta_identity_and_persistence(self):
        before = self.snapshot()
        # Every wishlist mutation is CSRF-protected and anonymous POSTs are rejected.
        for path in ('/wishlist/add/10', '/wishlist/remove/10', '/wishlist/toggle/10'):
            self.assertEqual(self.post(path, token=False).status_code, 400)
            self.assertEqual(self.snapshot(), before)
        self.login()
        # Idempotent endpoints (repair002, M8): repeating a save keeps exactly one row,
        # repeating a removal leaves none, so a double submit cannot reverse the intent.
        for _ in range(2):
            self.assertEqual(self.post('/wishlist/add/10',
                             headers={'Referer': 'http://localhost/where-to-buy/geforce-rtx-4060'}).status_code, 302)
        added = self.snapshot()['wishlist_items']
        self.assertEqual([row for row in added if row not in before['wishlist_items']],
                         [(max(row[0] for row in added), 1, 10)])
        for _ in range(2):
            self.assertEqual(self.post('/wishlist/remove/10').status_code, 302)
        self.assertEqual(self.snapshot(), before)
        # Allowed product rows behave the same way on a different product.
        for _ in range(2):
            response = self.post('/wishlist/add/5',
                                 headers={'Referer': 'http://localhost/where-to-buy/geforce-rtx-5060-ti'})
            self.assertEqual(response.location, '/where-to-buy/geforce-rtx-5060-ti')
        after = self.snapshot()
        for name, rows in before.items():
            if name != 'wishlist_items':
                self.assertEqual(after[name], rows, name)
        additions = [row for row in after['wishlist_items'] if row not in before['wishlist_items']]
        self.assertEqual({(r[1], r[2]) for r in additions}, {(1, 5)})
        for _ in range(2):
            page = self.get('/account/wishlist')
            self.assertIn('GeForce RTX 5060 Ti 16GB', page)
        self.post('/logout')
        self.login('bob.c@test.com')
        self.assertIn('Your wishlist is empty', self.get('/account/wishlist'))
        self.post('/logout')
        self.login()
        self.post('/wishlist/add/10', headers={'Referer': 'http://localhost/'})
        self.assertIn('GeForce RTX 4060', self.get('/account/wishlist'))
        # Compatibility toggle still flips exactly once per request.
        self.post('/wishlist/toggle/10')
        self.post('/wishlist/toggle/5')
        self.assertEqual(self.snapshot(), before)
        # A non-local Referer never becomes the redirect target.
        response = self.post('/wishlist/add/10', headers={'Referer': 'https://example.com/'})
        self.assertEqual(urlsplit(response.location).netloc, '')
        self.assertEqual(response.location, '/products/geforce-rtx-4060')
        self.post('/wishlist/remove/10')

    def test_05_jetson_price_and_spec_contract(self):
        for slug, identity, memory in (('jetson-orin-nano-super', 'developer kit', '8 GB'),
                                       ('jetson-orin-nx', 'production module', '16 GB')):
            text = Markup(self.get('/products/' + slug)).text
            self.assertIn(identity, text)
            self.assertIn(memory, text)
        compare = self.get('/compare?product=jetson-orin-nano-super&product=jetson-orin-nx')
        legacy = self.get('/compare?ids=jetson-orin-nano-super,jetson-orin-nx')
        for page in (compare, legacy):
            for fact in ('developer kit', 'production module', '8 GB', '16 GB'):
                self.assertIn(fact, page)
        with module.app.app_context():
            ti = module.Product.query.filter_by(slug='geforce-rtx-5060-ti').one()
            gpu = module.Product.query.filter_by(slug='geforce-rtx-5060').one()
            self.assertEqual((ti.name, ti.memory_gb, ti.price_usd, ti.recommended_psu_watts),
                             ('GeForce RTX 5060 Ti 16GB', 16, 429, 600))
            self.assertEqual(gpu.recommended_psu_watts, 550)
        self.assertIn('Ryzen 9 9950X', self.get('/products/geforce-rtx-5060-ti'))
        home = self.get('/')
        self.assertIn('Jetson Orin Nano Super Developer Kit', home)
        self.assertIn('$249', home)

    def test_06_header_forms_and_driver_structure(self):
        for signed_in in (False, True):
            if signed_in:
                self.login()
            page = Markup(self.get('/'))
            self.assertTrue(any(d.get('class') == 'site-menu' for d in page.attrs('details')))
            self.assertTrue(page.attrs('summary'))
            self.assertTrue(any(i.get('type') == 'search' for i in page.attrs('input')))
            links = [a.get('href') for a in page.attrs('a')]
            self.assertIn('/account' if signed_in else '/login', links)
            self.assertIn('/account/wishlist', links)
            self.assertNotIn('/cart', links)
        driver = self.get('/drivers?series=GeForce+RTX+50+Series&branch=Game+Ready&os=Windows+11')
        for text in ('566.36', 'Jun 10, 2026', '712 MB', 'Selected:', 'Clear Filters'):
            self.assertIn(text, driver)
        self.assertTrue(any(d.get('tabindex') == '0' and d.get('aria-label') == 'Driver results'
                            for d in Markup(driver).attrs('div')))
        self.assertIn('No drivers match', self.get('/drivers?series=GeForce+RTX+50+Series&os=Linux'))
        css = (copy / 'static/css/main.css').read_text()
        for text in ('@media(max-width:600px)', 'grid-template-columns:1fr',
                     'object-fit:contain', 'overflow-x:auto', '.searchbox input'):
            self.assertIn(text, css)
        self.assertNotIn('.nav{display:none}', css)

    def test_06b_review_rating_requires_explicit_selection(self):
        """The graded rating field must not arrive pre-answered (repair002, M11)."""
        self.login()
        page = Markup(self.get('/products/jetson-orin-nano-super'))
        rating = [field for field in page.attrs('select') if field.get('name') == 'rating'][0]
        del rating  # option order is checked on the raw page below
        raw = self.get('/products/jetson-orin-nano-super')
        block = raw[raw.index('name="rating"'):]
        block = block[:block.index('</select>')]
        self.assertIn('<option value="">Select a rating</option>', block)
        self.assertNotIn('selected', block)
        before = self.snapshot()
        self.post('/products/jetson-orin-nano-super/review',
                  {'rating': '', 'title': 'Incredible', 'body': 'No rating chosen.'})
        self.assertEqual(self.snapshot(), before)
        self.post('/wishlist/remove/5')

    def test_06c_session_cookie_cannot_be_forged_with_a_literal_key(self):
        """The signing key is not a committed literal (repair002, M4)."""
        from itsdangerous import URLSafeTimedSerializer

        def cookie_for(key):
            signer = URLSafeTimedSerializer(key, salt='cookie-session',
                                            signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'})
            return signer.dumps({'_user_id': '1', '_fresh': True})

        from flask.sessions import SecureCookieSessionInterface
        serializer = SecureCookieSessionInterface().get_signing_serializer(module.app)

        def forge(key):
            client = module.app.test_client()
            value = serializer.dumps({'_user_id': '1', '_fresh': True}) if key == module.app.secret_key else \
                URLSafeTimedSerializer(key, salt='cookie-session',
                                       signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'}
                                       ).dumps({'_user_id': '1', '_fresh': True})
            client.set_cookie('session', value)
            return client.get('/account')

        # Control: the application's own key authenticates through this exact code path,
        # so a rejection below is about the key rather than the cookie transport.
        control = forge(module.app.secret_key)
        self.assertEqual(control.status_code, 200)
        self.assertIn('Alice Johnson', control.get_data(as_text=True))
        for literal in ('nvidia-mirror-dev-secret-key', 'nvidia-mirror-secret', 'secret'):
            response = forge(literal)
            self.assertEqual(response.status_code, 302, literal)
            self.assertNotIn('Alice Johnson', response.get_data(as_text=True), literal)

    def test_06d_logout_requires_post(self):
        """GET/HEAD logout is refused so a prefetch cannot end the session (repair002, M5)."""
        self.login()
        self.get('/logout', 405)
        self.assertEqual(self.client.head('/logout').status_code, 405)
        self.assertIn('Alice Johnson', self.get('/account'))
        page = Markup(self.get('/'))
        forms = [form for form in page.attrs('form') if form.get('action') == '/logout']
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0].get('method'), 'post')
        self.post('/logout')
        self.get('/account', 302)
        self.login()

    def test_07_form_regressions_and_local_returns(self):
        wrong = self.post('/login', {'email': 'alice.j@test.com', 'password': 'wrong'})
        self.assertIn('Invalid email or password', wrong.get_data(as_text=True))
        for target in ('https://example.com/', '//example.com/', '/\\example.com', 'javascript:alert(1)'):
            from urllib.parse import urlencode
            response = self.login(query='?' + urlencode({'next': target}))
            self.assertEqual(response.location, '/account')
            self.post('/logout')
        self.assertEqual(self.login(query='?next=/where-to-buy/geforce-rtx-5080').location,
                         '/where-to-buy/geforce-rtx-5080')
        # Browser flow: the login form posts to /login without the query string,
        # so the hidden next field must carry the user back to where they came from.
        self.post('/logout')
        page = Markup(self.get('/login?next=/products/geforce-rtx-5090'))
        self.assertEqual([field.get('value') for field in page.attrs('input')
                          if field.get('name') == 'next'], ['/products/geforce-rtx-5090'])
        response = self.post('/login', {'email': 'alice.j@test.com', 'password': 'TestPass123!',
                                        'next': '/products/geforce-rtx-5090'})
        self.assertEqual(response.location, '/products/geforce-rtx-5090')
        self.post('/logout')
        self.login()
        self.get('/account/edit')
        self.assertEqual(self.post('/account/edit', {'name': 'Alice Johnson', 'company': 'Pixel Forge Studios',
                         'country': 'Germany', 'newsletter_opt_in': 'y'}).status_code, 302)
        self.assertIn('Germany', self.get('/account'))
        self.assertIn('Historical local demo record', self.get('/order/1'))
        self.get('/order/2', 403)
        self.assertEqual(self.post('/products/jetson-orin-nano-super/review',
                         {'rating': '5', 'title': 'Incredible', 'body': 'Local demo review.'}).status_code, 302)
        self.assertIn('Incredible', self.get('/products/jetson-orin-nano-super'))
        response = self.post('/wishlist/toggle/10', headers={'Referer': 'https://example.com/'})
        self.assertEqual(urlsplit(response.location).netloc, '')
        self.assertEqual(response.location, '/products/geforce-rtx-4060')

    def test_08b_seed_passwords_are_pinned(self):
        """Demo password hashes are pinned so a regenerated seed is deterministic (repair002, L4)."""
        import seed_data
        self.assertTrue(seed_data.BENCHMARK_USERS)
        for user in seed_data.BENCHMARK_USERS:
            self.assertIn('password_hash', user, user['email'])
            self.assertTrue(module.bcrypt.check_password_hash(user['password_hash'], user['password']),
                            user['email'])
            with module.app.app_context():
                stored = module.User.query.filter_by(email=user['email']).one()
                self.assertEqual(stored.password_hash, user['password_hash'], user['email'])
        with module.app.app_context():
            module.seed_benchmark_users()   # gated: a no-op must leave the hashes untouched
            for user in seed_data.BENCHMARK_USERS:
                self.assertEqual(module.User.query.filter_by(email=user['email']).one().password_hash,
                                 user['password_hash'], user['email'])

    def test_09_contrast_tokens(self):
        """Stylesheet-derived WCAG checks (repair002, M1/M2)."""
        css = (copy / 'static/css/main.css').read_text()

        def token(name):
            match = re.search(name + r'\s*:\s*(#[0-9a-fA-F]{6})', css)
            self.assertIsNotNone(match, name)
            return match.group(1)

        def channel(value):
            value = value / 255
            return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

        def luminance(colour):
            r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
            return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

        def ratio(a, b):
            la, lb = luminance(a), luminance(b)
            high, low = max(la, lb), min(la, lb)
            return (high + 0.05) / (low + 0.05)

        action, focus, star, brand = token('--action'), token('--focus'), token('--star'), token('--brand')
        for background in ('#ffffff', '#f7f7f7'):
            self.assertGreaterEqual(round(ratio(action, background), 3), 4.5, f'{action} on {background}')
            self.assertGreaterEqual(round(ratio(star, background), 3), 4.5, f'{star} on {background}')
        for background in ('#ffffff', '#f7f7f7', '#000000', '#111111', '#1a1a1a'):
            self.assertGreaterEqual(round(ratio(focus, background), 3), 3.0, f'{focus} on {background}')
        # The brand colour stays decorative: it must not be used for text on light surfaces.
        for selector in ('a:hover', '.card .series', '.green{', '.news-card .cat', '.pill.active'):
            index = css.index(selector)
            rule = css[index:css.index('}', index)]
            self.assertIn('var(--action)', rule, selector)
            self.assertNotIn('var(--nv-green', rule, selector)
        self.assertIn('outline:3px solid var(--focus)', css)

    def test_08_seed_and_import_byte_identity(self):
        before = digest(database)
        with module.app.app_context():
            for _ in range(2):
                module.seed_catalog()
                module.seed_articles()
                module.seed_drivers()
                module.seed_benchmark_users()
                module.seed_reviews()
                module.seed_benchmark_activity()
            module.db.session.remove()
            module.db.engine.dispose()
        self.assertEqual(digest(database), before)
        command = [sys.executable, '-B', '-c', 'import app']
        proc = subprocess.run(command, cwd=copy, capture_output=True, text=True)
        imports.append({'command': command, 'cwd': str(copy), 'exit': proc.returncode,
                        'stdout': proc.stdout, 'stderr': proc.stderr,
                        'before_sha256': before, 'after_sha256': digest(database)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(digest(database), before)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--references', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    source = Path(__file__).resolve().parent
    if output == source or source in output.parents:
        parser.error('--output must be outside the source directory')
    if output.exists() or not output.parent.is_dir():
        parser.error('--output must be new and have an existing parent directory')
    output.mkdir(mode=0o700)
    (output / 'html').mkdir()
    copy = output / 'source-copy'
    copy.mkdir()
    files = source_files(source)
    hashes = {str(p.relative_to(source)): digest(p) for p in files}
    source_runtime_before = {str(p.relative_to(source)): digest(p)
                             for folder in ('instance', 'instance_seed', '__pycache__')
                             for p in (source / folder).rglob('*') if p.is_file()}
    for path in files:
        dest = copy / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    references = args.references.resolve() if args.references else None
    sys.path.insert(0, str(copy))
    module = importlib.import_module('app')
    module.app.config['TESTING'] = True
    database = copy / 'instance/nvidia.db'
    seed = output / 'baseline.db'
    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()
    shutil.copyfile(database, seed)
    routes, imports = [], []
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(UIContract))
    text = stream.getvalue()
    print(text, end='')
    (output / 'tests.log').write_text(text)
    source_runtime_after = {str(p.relative_to(source)): digest(p)
                            for folder in ('instance', 'instance_seed', '__pycache__')
                            for p in (source / folder).rglob('*') if p.is_file()}
    unchanged = hashes == {str(p.relative_to(source)): digest(p) for p in files}
    runtime_unchanged = source_runtime_before == source_runtime_after
    success = result.wasSuccessful() and unchanged and runtime_unchanged
    report = {'kind': 'mechanical-test-client-not-browser', 'command': sys.orig_argv,
              'exit': 0 if success else 1, 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'source_sha256': hashes, 'source_unchanged': unchanged,
              'source_set_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True,
                                                            separators=(',', ':')).encode()).hexdigest(),
              'source_runtime_unchanged': runtime_unchanged, 'baseline_db_sha256': digest(seed),
              'routes': routes, 'imports': imports,
              'reference_html_sha256': {str(p.relative_to(references)): digest(p)
                                       for p in references.glob('*/response.body')} if references else {}}
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    sys.exit(report['exit'])
