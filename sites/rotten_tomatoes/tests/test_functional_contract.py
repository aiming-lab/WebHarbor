"""Regression tests for the closed Rotten Tomatoes functional findings.

Run with ``python -m unittest discover -s sites/rotten_tomatoes/tests -v``.
When running this file outside that directory, set ROTTEN_TOMATOES_SOURCE to
the site directory. Source files are copied into a TemporaryDirectory before
import; no source, runtime, or seed database is opened or modified.
"""

import concurrent.futures
import importlib.util
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import types
import unittest
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

import bcrypt as bcrypt_backend
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError


class Element:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def descendants(self, tag=None):
        for child in self.children:
            if isinstance(child, Element):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.descendants(tag)

    def text(self):
        return ''.join(child.text() if isinstance(child, Element) else child
                       for child in self.children)


class Document(HTMLParser):
    VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element('document')
        self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        child = Element(tag, attrs, self.current)
        self.current.children.append(child)
        if tag not in self.VOID_TAGS:
            self.current = child

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Element(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


class FunctionalContractTests(unittest.TestCase):
    PASSWORD = 'TestPass123!'
    ALICE_EMAIL = 'alice.j@test.com'
    BOB_EMAIL = 'bob.c@test.com'
    SLUG = 'functional-fixture'
    MOVIE_PATH = '/m/' + SLUG
    RATE_PATH = MOVIE_PATH + '/rate'
    REVIEW_PATH = MOVIE_PATH + '/review'
    ADD_PATH = '/user/watchlist/add/1'
    REMOVE_PATH = '/user/watchlist/remove/1'
    REVIEW_TEXT = 'A complete review for this isolated fixture.'

    @classmethod
    def setUpClass(cls):
        source_override = os.environ.get('ROTTEN_TOMATOES_SOURCE')
        source = Path(source_override) if source_override else Path(__file__).resolve().parents[1]
        if not (source / 'app.py').is_file():
            raise RuntimeError('Set ROTTEN_TOMATOES_SOURCE to the Rotten Tomatoes site directory')
        cls.scratch = tempfile.TemporaryDirectory(prefix='rotten-tomatoes-contract-')
        cls.addClassCleanup(cls.scratch.cleanup)
        fixture = Path(cls.scratch.name)
        shutil.copy2(source / 'app.py', fixture / 'app.py')
        shutil.copytree(source / 'templates', fixture / 'templates')

        # The only stub is the seed loader: the real app initializes its normal
        # schema in the scratch directory, and all requests use real routes.
        seed_stub = types.ModuleType('seed_data')
        seed_stub.seed_all = lambda *args, **kwargs: None
        module_name = '_rotten_tomatoes_functional_fixture'
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
        cls.app, cls.db = cls.site.app, cls.site.db
        cls.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
        # Build an ordinary legacy bcrypt hash independently of app settings;
        # changing the app's password interpretation must break this fixture.
        cls.password_hash = bcrypt_backend.hashpw(
            cls.PASSWORD.encode('utf-8'), bcrypt_backend.gensalt()).decode('utf-8')

        def dispose_engine():
            with cls.app.app_context():
                cls.db.session.remove()
                cls.db.engine.dispose()

        cls.addClassCleanup(dispose_engine)

    def setUp(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()
            self.db.create_all()
            self.db.session.add_all([
                self.site.User(id=1, email=self.ALICE_EMAIL, name='Alice Jones',
                               password_hash=self.password_hash),
                self.site.User(id=2, email=self.BOB_EMAIL, name='Bob Clark',
                               password_hash=self.password_hash),
                self.site.Movie(id=1, title='Functional Fixture', slug=self.SLUG, year=2026),
            ])
            self.db.session.commit()

    def csrf_token(self, client):
        response = client.get('/account/edit', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        inputs = Document(response.get_data(as_text=True)).root.descendants('input')
        tokens = [node.attrs.get('value') for node in inputs
                  if node.attrs.get('name') == 'csrf_token']
        self.assertTrue(tokens and tokens[0], 'GET form must issue a genuine CSRF token')
        return tokens[0]

    def post(self, client, path, data=None, **kwargs):
        payload = {'csrf_token': self.csrf_token(client), **(data or {})}
        return client.post(path, data=payload, **kwargs)

    def login(self, email=None, password=None, next_url=None):
        client = self.app.test_client()
        path = '/login'
        if next_url is not None:
            path += '?' + urlencode({'next': next_url})
        response = self.post(client, path, {
            'email': email or self.ALICE_EMAIL,
            'password': self.PASSWORD if password is None else password,
        })
        return client, response

    def signed_in(self, email=None):
        client, response = self.login(email=email)
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.session_user(client))
        return client

    def session_user(self, client):
        with client.session_transaction() as session:
            return session.get('_user_id')

    def register_payload(self, email, password=None, name='New Fixture User'):
        password = self.PASSWORD if password is None else password
        return {'email': email, 'name': name, 'password': password,
                'confirm_password': password}

    def state(self):
        with self.app.app_context():
            return {table.name: [tuple(row) for row in self.db.session.execute(
                table.select().order_by(*table.primary_key.columns)).all()]
                for table in self.db.metadata.sorted_tables}

    def rows(self, model, **filters):
        with self.app.app_context():
            rows = model.query.filter_by(**filters).order_by(model.id).all()
            return [{column.name: getattr(row, column.name)
                     for column in model.__table__.columns} for row in rows]

    def clear_rows(self, model):
        with self.app.app_context():
            model.query.delete()
            self.db.session.commit()

    def add_review(self, user_id=2, text=None, score=3.5):
        with self.app.app_context():
            review = self.site.AudienceReview(movie_id=1, user_id=user_id,
                                              score=score, text=text or self.REVIEW_TEXT)
            self.db.session.add(review)
            self.db.session.commit()
            return review.id

    def form(self, response, path):
        root = Document(response.get_data(as_text=True)).root
        for form in root.descendants('form'):
            action = form.attrs.get('action', '')
            if urlsplit(action).path == path or (not action and path in ('/login', '/register')):
                return form
        self.fail(f'No form for {path} in HTTP {response.status_code} response')

    def errors(self, form):
        return [node for node in form.descendants()
                if ('error' in node.attrs.get('class', '').lower()
                    or node.attrs.get('role') == 'alert') and node.text().strip()]

    def assert_field_error(self, response, path, field):
        form = self.form(response, path)
        fields = [node for node in form.descendants()
                  if node.attrs.get('name') == field]
        self.assertTrue(fields, f'{field} input must remain present')
        self.assertTrue(self.errors(form), f'{field} validation must display an error in its form')
        return form

    def assert_local_redirect(self, response, expected=None):
        self.assertEqual(response.status_code, 302)
        location = response.headers['Location']
        target = urlsplit(location)
        self.assertFalse(target.scheme or target.netloc, location)
        self.assertNotIn('\\', location)
        self.assertFalse(location.startswith('//'), location)
        if expected is not None:
            self.assertEqual(location, expected)

    def test_login_preserves_safe_next_and_rejects_external_targets(self):
        safe = {
            '/account?from=login#profile': '/account?from=login#profile',
            'http://localhost/account?from=login#profile': '/account?from=login#profile',
            'account?from=login#profile': '/account?from=login#profile',
        }
        for target, expected in safe.items():
            with self.subTest(target=target):
                _, response = self.login(next_url=target)
                self.assert_local_redirect(response, expected)
        for target in ('https://example.invalid/landing', '//example.invalid/landing',
                       '/\\example.invalid/landing', 'javascript:alert(1)',
                       'http://localhost//example.invalid/path',
                       'http:////example.invalid/path',
                       'http://localhost/%2Fexample.invalid/path',
                       '/account\r\nLocation: https://example.invalid/'):
            with self.subTest(target=target):
                _, response = self.login(next_url=target)
                self.assert_local_redirect(response, '/')

    def test_watchlist_preserves_safe_next_and_rejects_unsafe_next_and_referrer(self):
        client = self.signed_in()
        response = self.post(client, self.ADD_PATH, {'next': '../../watchlist'})
        self.assert_local_redirect(response, '/user/watchlist')
        for target in ('/user/watchlist?sort=recent#top',
                       'http://localhost/user/watchlist?sort=recent#top'):
            with self.subTest(target=target):
                response = self.post(client, self.ADD_PATH, {'next': target})
                self.assert_local_redirect(response, '/user/watchlist?sort=recent#top')
        for mode in ('next', 'referrer'):
            for target in ('https://example.invalid/landing', '//example.invalid/landing',
                           '/\\example.invalid/landing',
                           'http://localhost//example.invalid/path',
                           'http:////example.invalid/path',
                           'http://localhost/%2Fexample.invalid/path'):
                with self.subTest(mode=mode, target=target):
                    data = {'next': target} if mode == 'next' else {}
                    headers = {'Referer': target} if mode == 'referrer' else {}
                    response = self.post(client, self.ADD_PATH, data, headers=headers)
                    self.assert_local_redirect(response, self.MOVIE_PATH)
        response = self.post(client, self.REMOVE_PATH,
                             headers={'Referer': 'https://example.invalid/user/watchlist'})
        self.assert_local_redirect(response)

    def test_demo_password_still_authenticates_existing_hash(self):
        for email, user_id in ((self.ALICE_EMAIL, '1'), (self.BOB_EMAIL, '2')):
            with self.subTest(email=email):
                client, response = self.login(email=email)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.session_user(client), user_id)

    def test_registration_and_login_accept_exactly_72_utf8_bytes(self):
        for index, password in enumerate(('x' * 72, '界' * 24)):
            with self.subTest(password_bytes=len(password.encode('utf-8'))):
                email = f'boundary{index}@example.com'
                client = self.app.test_client()
                response = self.post(client, '/register', self.register_payload(email, password))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(len(self.rows(self.site.User, email=email)), 1)
                logged_in, response = self.login(email=email, password=password)
                self.assertEqual(response.status_code, 302)
                self.assertIsNotNone(self.session_user(logged_in))

    def test_registration_and_login_reject_73_utf8_bytes_with_visible_error(self):
        for index, password in enumerate(('x' * 73, '界' * 24 + 'x')):
            for path in ('/register', '/login'):
                with self.subTest(path=path, password_bytes=len(password.encode('utf-8'))):
                    client = self.app.test_client()
                    before = self.state()
                    payload = (self.register_payload(f'toolong{index}@example.com', password)
                               if path == '/register' else
                               {'email': self.ALICE_EMAIL, 'password': password})
                    response = self.post(client, path, payload)
                    self.assertIn(response.status_code, (200, 400, 422))
                    self.assert_field_error(response, path, 'password')
                    self.assertIsNone(self.session_user(client))
                    self.assertEqual(self.state(), before)

    def test_registration_invalid_data_and_duplicate_email_never_authenticate(self):
        payloads = [self.register_payload('not-an-email'),
                    self.register_payload('short@example.com', 'abc'),
                    self.register_payload(self.ALICE_EMAIL.upper())]
        for payload in payloads:
            with self.subTest(email=payload['email']):
                before = self.state()
                client = self.app.test_client()
                response = self.post(client, '/register', payload)
                self.assertIn(response.status_code, (200, 400, 409, 422))
                self.assertIsNone(self.session_user(client))
                self.assertEqual(self.state(), before)

    def test_invalid_ratings_return_422_and_errors_only_in_rating_form(self):
        client = self.signed_in()
        for score in ('', 'abc', '0', '0.49', '5.01', '-1', 'NaN', 'nan',
                      'Infinity', '-inf', '1e309'):
            with self.subTest(score=score):
                before = self.state()
                response = self.post(client, self.RATE_PATH, {'score': score})
                self.assertEqual(response.status_code, 422)
                self.assert_field_error(response, self.RATE_PATH, 'score')
                self.assertFalse(self.errors(self.form(response, self.REVIEW_PATH)))
                self.assertEqual(self.state(), before)

    def test_invalid_review_scores_return_422_and_preserve_draft(self):
        client = self.signed_in()
        draft = 'Preserve this draft: <strong>safe & literal</strong>.'
        for score in ('', 'abc', '0.49', '5.01', 'NaN', 'Infinity', '-inf', '1e309'):
            with self.subTest(score=score):
                before = self.state()
                response = self.post(client, self.REVIEW_PATH, {'score': score, 'text': draft})
                self.assertEqual(response.status_code, 422)
                form = self.assert_field_error(response, self.REVIEW_PATH, 'score')
                textarea = next(form.descendants('textarea'))
                self.assertEqual(textarea.text(), draft)
                self.assertFalse(list(textarea.descendants()), 'Draft markup must be escaped')
                self.assertFalse(self.errors(self.form(response, self.RATE_PATH)))
                self.assertEqual(self.state(), before)

    def test_review_text_boundaries_preserve_invalid_draft_and_selected_score(self):
        client = self.signed_in()
        for length in (0, 9, 2001):
            with self.subTest(length=length):
                before = self.state()
                draft = 'x' * length
                response = self.post(client, self.REVIEW_PATH, {'score': '4', 'text': draft})
                self.assertEqual(response.status_code, 422)
                form = self.assert_field_error(response, self.REVIEW_PATH, 'text')
                textarea = next(form.descendants('textarea'))
                self.assertEqual(textarea.text(), draft)
                self.assertEqual(textarea.attrs.get('maxlength'), '2000')
                selected = [node.attrs['value'] for node in form.descendants('option')
                            if 'selected' in node.attrs]
                self.assertEqual([float(value) for value in selected], [4.0])
                self.assertFalse(self.errors(self.form(response, self.RATE_PATH)))
                self.assertEqual(self.state(), before)
        for length in (10, 2000):
            with self.subTest(length=length):
                self.clear_rows(self.site.AudienceReview)
                response = self.post(client, self.REVIEW_PATH, {'score': '4', 'text': 'x' * length})
                self.assert_local_redirect(response, self.MOVIE_PATH)
                rows = self.rows(self.site.AudienceReview, user_id=1, movie_id=1)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['text'], 'x' * length)

    def test_legal_rating_bounds_and_repeated_rating_update_one_row(self):
        client = self.signed_in()
        for score in ('0.5', '5', '3.5'):
            with self.subTest(score=score):
                response = self.post(client, self.RATE_PATH, {'score': score})
                self.assert_local_redirect(response, self.MOVIE_PATH)
                rows = self.rows(self.site.UserRating, user_id=1, movie_id=1)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['score'], float(score))
                self.clear_rows(self.site.AudienceReview)
                response = self.post(client, self.REVIEW_PATH,
                                     {'score': score, 'text': self.REVIEW_TEXT})
                self.assert_local_redirect(response, self.MOVIE_PATH)
                reviews = self.rows(self.site.AudienceReview, user_id=1, movie_id=1)
                self.assertEqual(len(reviews), 1)
                self.assertEqual(reviews[0]['score'], float(score))

    def test_repeated_watchlist_and_review_do_not_duplicate_or_overwrite(self):
        client = self.signed_in()
        for index in range(3):
            self.assertEqual(self.post(client, self.ADD_PATH).status_code, 302)
            response = self.post(client, self.REVIEW_PATH,
                                 {'score': '4' if index == 0 else '1',
                                  'text': self.REVIEW_TEXT if index == 0 else 'A replacement draft.'})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.rows(self.site.WatchlistItem, user_id=1, movie_id=1)), 1)
        rows = self.rows(self.site.AudienceReview, user_id=1, movie_id=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['text'], rows[0]['score']), (self.REVIEW_TEXT, 4.0))

    def test_account_name_validates_trimmed_2_to_120_characters(self):
        client = self.signed_in()
        for name in ('xy', 'x' * 120, '  Alice Trimmed  '):
            with self.subTest(name_length=len(name)):
                response = self.post(client, '/account/edit', {'name': name})
                self.assert_local_redirect(response, '/account')
                self.assertEqual(self.rows(self.site.User, id=1)[0]['name'], name.strip())
        for name in ('', ' ', 'x', 'x' * 121, 'x' * 10000):
            with self.subTest(name_length=len(name)):
                before = self.state()
                response = self.post(client, '/account/edit', {'name': name})
                self.assertIn(response.status_code, (200, 400, 422))
                text = Document(response.get_data(as_text=True)).root.text()
                self.assertRegex(text, r'(?i)name.{0,100}(2|120|characters)')
                self.assertEqual(self.state(), before)

    def write_endpoints(self, review_id):
        return [('/login', {'email': self.ALICE_EMAIL, 'password': self.PASSWORD}),
                ('/register', self.register_payload('csrf-new@example.com')),
                ('/account/edit', {'name': 'Changed Name'}),
                (self.ADD_PATH, {}), (self.REMOVE_PATH, {}),
                (self.RATE_PATH, {'score': '4'}),
                (self.REVIEW_PATH, {'score': '4', 'text': self.REVIEW_TEXT}),
                (f'/user/reviews/delete/{review_id}', {}), ('/logout', {})]

    def test_all_post_routes_reject_missing_invalid_and_other_session_csrf(self):
        alice = self.signed_in()
        bob = self.signed_in(self.BOB_EMAIL)
        review_id = self.add_review(user_id=1)
        other_token = self.csrf_token(bob)
        self.csrf_token(alice)
        for path, data in self.write_endpoints(review_id):
            for mode in ('missing', 'invalid', 'other-session'):
                with self.subTest(path=path, mode=mode):
                    payload = dict(data)
                    if mode != 'missing':
                        payload['csrf_token'] = other_token if mode == 'other-session' else 'invalid-token'
                    before = self.state()
                    response = alice.post(path, data=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(self.state(), before)
                    self.assertEqual(self.session_user(alice), '1')

    def test_authenticated_writes_require_login_even_with_valid_csrf(self):
        review_id = self.add_review()
        for path, data in self.write_endpoints(review_id)[2:-1]:
            with self.subTest(path=path):
                before = self.state()
                response = self.post(self.app.test_client(), path, data)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.location).path, '/login')
                self.assertEqual(self.state(), before)

    def test_forged_user_ids_do_not_change_other_users_objects(self):
        alice = self.signed_in()
        bob_review_id = self.add_review(user_id=2)
        before_bob = {model.__tablename__: self.rows(model, user_id=2)
                      for model in (self.site.WatchlistItem, self.site.UserRating, self.site.AudienceReview)}
        for path, data in ((self.ADD_PATH, {}), (self.RATE_PATH, {'score': '4'}),
                           (self.REVIEW_PATH, {'score': '4', 'text': self.REVIEW_TEXT})):
            response = self.post(alice, path, {**data, 'user_id': '2'})
            self.assertEqual(response.status_code, 302)
        for model in (self.site.WatchlistItem, self.site.UserRating, self.site.AudienceReview):
            self.assertEqual(self.rows(model, user_id=2), before_bob[model.__tablename__])
            self.assertEqual(len(self.rows(model, user_id=1, movie_id=1)), 1)
        before = self.state()
        response = self.post(alice, f'/user/reviews/delete/{bob_review_id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.state(), before)
        response = self.post(alice, '/account/edit', {'name': 'Alice Changed', 'user_id': '2'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.rows(self.site.User, id=2)[0]['name'], 'Bob Clark')
        self.assertEqual(self.rows(self.site.User, id=1)[0]['name'], 'Alice Changed')

    def test_invalid_object_ids_and_slugs_return_404_without_writes(self):
        client = self.signed_in()
        for path in ('/user/watchlist/add/999999999', '/user/watchlist/remove/999999999',
                     '/m/missing-fixture/rate', '/m/missing-fixture/review',
                     '/user/reviews/delete/999999999', '/user/watchlist/add/-1',
                     '/user/watchlist/add/not-an-id', '/user/reviews/delete/0'):
            with self.subTest(path=path):
                before = self.state()
                response = self.post(client, path, {'score': '4', 'text': self.REVIEW_TEXT})
                self.assertEqual(response.status_code, 404)
                self.assertEqual(self.state(), before)

    def test_logout_requires_post_and_a_valid_session_csrf_token(self):
        client = self.signed_in()
        response = client.get('/logout')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.session_user(client), '1')
        response = self.post(client, '/logout')
        self.assert_local_redirect(response, '/')
        self.assertIsNone(self.session_user(client))

    def concurrent_posts(self, table_name, path, clients, payloads):
        """Rendezvous before real INSERTs, including SQLite upsert statements.

        Both requests have reached the conflicting write before either executes
        it. No route, query result, application function, or CSRF check is mocked.
        """
        payloads = [{'csrf_token': self.csrf_token(client), **payload}
                    for client, payload in zip(clients, payloads)]
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        arrived = set()
        insert = re.compile(r'^\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+["`\[]?'
                            + re.escape(table_name) + r'(?:["`\]]|\s|\()', re.I)

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if not insert.match(statement):
                return
            thread_id = threading.get_ident()
            with lock:
                first_insert = thread_id not in arrived
                arrived.add(thread_id)
            if first_insert:
                barrier.wait(timeout=15)

        with self.app.app_context():
            engine = self.db.engine
        event.listen(engine, 'before_cursor_execute', before_cursor_execute)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(client.post, path, data=payload)
                           for client, payload in zip(clients, payloads)]
                responses = [future.result(timeout=25) for future in futures]
        finally:
            event.remove(engine, 'before_cursor_execute', before_cursor_execute)
        self.assertEqual(len(arrived), 2, 'Both requests must actually reach the INSERT barrier')
        self.assertTrue(all(response.status_code < 500 for response in responses),
                        [response.status_code for response in responses])
        return responses

    def test_concurrent_registration_creates_one_user_and_never_logs_in_loser(self):
        email = 'same-registration@example.com'
        clients = [self.app.test_client(), self.app.test_client()]
        payloads = [self.register_payload(email, 'FirstPass123!', 'First Applicant'),
                    self.register_payload(email.upper(), 'SecondPass123!', 'Second Applicant')]
        responses = self.concurrent_posts('users', '/register', clients, payloads)
        rows = self.rows(self.site.User, email=email)
        self.assertEqual(len(rows), 1)
        winner = next(index for index, payload in enumerate(payloads) if payload['name'] == rows[0]['name'])
        self.assertEqual(responses[winner].status_code, 302)
        self.assertEqual(self.session_user(clients[winner]), str(rows[0]['id']))
        self.assertIsNone(self.session_user(clients[1 - winner]))
        self.assertIn(responses[1 - winner].status_code, (200, 400, 409, 422))
        self.assertIn('already', responses[1 - winner].get_data(as_text=True).lower())
        self.assertTrue(self.site.bcrypt.check_password_hash(rows[0]['password_hash'], payloads[winner]['password']))
        self.assertFalse(self.site.bcrypt.check_password_hash(rows[0]['password_hash'], payloads[1 - winner]['password']))

    def test_concurrent_watchlist_additions_create_one_row(self):
        clients = [self.signed_in(), self.signed_in()]
        responses = self.concurrent_posts('watchlist_items', self.ADD_PATH, clients, [{}, {}])
        self.assertEqual([response.status_code for response in responses], [302, 302])
        self.assertEqual(len(self.rows(self.site.WatchlistItem, user_id=1, movie_id=1)), 1)

    def test_concurrent_ratings_create_one_row_with_a_submitted_score(self):
        clients = [self.signed_in(), self.signed_in()]
        responses = self.concurrent_posts('user_ratings', self.RATE_PATH, clients,
                                          [{'score': '1.5'}, {'score': '4.5'}])
        self.assertEqual([response.status_code for response in responses], [302, 302])
        rows = self.rows(self.site.UserRating, user_id=1, movie_id=1)
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]['score'], (1.5, 4.5))
        response = self.post(clients[0], self.RATE_PATH, {'score': '3.5'})
        self.assertEqual(response.status_code, 302)
        updated = self.rows(self.site.UserRating, user_id=1, movie_id=1)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]['score'], 3.5)

    def test_concurrent_reviews_keep_one_complete_submission(self):
        clients = [self.signed_in(), self.signed_in()]
        payloads = [{'score': '1.5', 'text': 'The first submitted review.'},
                    {'score': '4.5', 'text': 'The second submitted review.'}]
        responses = self.concurrent_posts('audience_reviews', self.REVIEW_PATH, clients, payloads)
        self.assertEqual([response.status_code for response in responses], [302, 302])
        rows = self.rows(self.site.AudienceReview, user_id=1, movie_id=1)
        self.assertEqual(len(rows), 1)
        self.assertIn((rows[0]['score'], rows[0]['text']),
                      [(float(payload['score']), payload['text']) for payload in payloads])

    def test_fresh_schema_enforces_unique_review_user_movie_pair(self):
        self.add_review(user_id=1)
        with self.app.app_context():
            self.db.session.add(self.site.AudienceReview(movie_id=1, user_id=1,
                                                        score=2, text='A duplicate fixture review.'))
            with self.assertRaises(IntegrityError):
                self.db.session.commit()
            self.db.session.rollback()
        self.assertEqual(len(self.rows(self.site.AudienceReview, user_id=1, movie_id=1)), 1)


    def test_unknown_public_scores_do_not_break_status_or_actor_extrema(self):
        with self.app.app_context():
            unknown = self.db.session.get(self.site.Movie, 1)
            unknown.tomatometer = None
            unknown.audience_score = None
            self.assertEqual(unknown.tomatometer_status, 'empty')
            self.assertEqual(unknown.audience_status, 'empty')
            self.assertEqual(unknown.tomatometer_icon, '')
            self.assertEqual(unknown.audience_icon, '')
            actor = self.site.Person(id=1, name='Fixture Actor', slug='fixture-actor')
            self.db.session.add(actor)
            self.db.session.add(self.site.MovieCast(movie=unknown, person=actor))
            self.db.session.flush()
            self.assertIsNone(actor.highest_rated_movie)
            self.assertIsNone(actor.lowest_rated_movie)
            known = self.site.Movie(id=2, title='Known Score', slug='known-score', year=2026,
                                    tomatometer=80, audience_score=70)
            self.db.session.add_all([known, self.site.MovieCast(movie=known, person=actor)])
            self.db.session.flush()
            self.assertEqual(actor.highest_rated_movie.id, 2)
            self.assertEqual(actor.lowest_rated_movie.id, 2)
            self.assertEqual(known.tomatometer_status, 'fresh')
            self.assertEqual(known.audience_status, 'upright')


    def test_people_search_uses_verified_credits_and_accent_normalization(self):
        with self.app.app_context():
            movie = self.db.session.get(self.site.Movie, 1)
            movie.producer = 'Kevin Feige'
            actor = self.site.Person(name='Timothée Chalamet', slug='timothee-chalamet')
            self.db.session.add_all([actor, self.site.MovieCast(movie=movie, person=actor)])
            self.db.session.commit()
            self.assertEqual([m.id for m in self.site.search_movies('Kevin Feige')], [1])
            self.assertEqual([m.id for m in self.site.search_movies('Timothee Chalamet')], [1])
            self.assertEqual([p.name for p in self.site.search_people('Timothee Chalamet')], ['Timothée Chalamet'])
        response = self.app.test_client().get('/search?search=Kevin+Feige')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.MOVIE_PATH, response.get_data(as_text=True))

    def test_subscription_filter_uses_membership_and_rentals_remain_at_home(self):
        with self.app.app_context():
            self.db.session.add_all([
                self.site.Movie(id=2, title='Both Services', slug='both', year=2026,
                                streaming_platform='Disney+, Max', available_at_home=True),
                self.site.Movie(id=3, title='Rental Only', slug='rental', year=2026,
                                streaming_platform='', available_at_home=True,
                                watch_description='Rent on Fandango.'),
                self.site.Movie(id=4, title='Disney Alone', slug='disney', year=2026,
                                streaming_platform='Disney+', available_at_home=True),
                self.site.Movie(id=5, title='Unknown Offers', slug='unknown', year=2026),
            ])
            self.db.session.commit()
        client = self.app.test_client()
        all_home = client.get('/browse/movies_at_home/').get_data(as_text=True)
        for title in ['Both Services', 'Rental Only', 'Disney Alone']:
            self.assertIn(title, all_home)
        self.assertNotIn('Unknown Offers', all_home)
        selected = client.get('/browse/movies_at_home/?platform=Max').get_data(as_text=True)
        self.assertIn('Both Services', selected)
        self.assertNotIn('Rental Only', selected)
        self.assertNotIn('Disney Alone', selected)
        self.assertNotIn('value="Disney+, Max"', selected)
        self.assertNotIn('Both Services', client.get('/browse/movies_at_home/?platform=%25').get_data(as_text=True))

    def test_unknown_public_facts_render_without_fake_zero_or_none_text(self):
        with self.app.app_context():
            movie = self.db.session.get(self.site.Movie, 1)
            movie.tomatometer = None
            movie.audience_score = None
            movie.pg_rating = None
            self.db.session.commit()
        response = self.app.test_client().get(self.MOVIE_PATH)
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('No Tomatometer score', page)
        self.assertNotIn('None%', page)
        self.assertNotIn('>0%</div>', page)
        self.assertNotIn('PG-13', page)


    def test_filmography_groups_roles_and_sorts_unknown_scores_last(self):
        with self.app.app_context():
            person = self.site.Person(name='Fixture Actor', slug='fixture-actor')
            unknown = self.site.Movie(title='Unknown score fixture', slug='unknown-score', year=2025)
            movie = self.db.session.get(self.site.Movie, 1)
            movie.tomatometer = 0
            movie.audience_score = 0
            self.db.session.add_all([person, unknown])
            self.db.session.flush()
            self.db.session.add_all([
                self.site.MovieCast(movie=movie, person=person, role_type='actor', character_name='Lead'),
                self.site.MovieCast(movie=movie, person=person, role_type='producer'),
                self.site.MovieCast(movie=unknown, person=person, role_type='actor')])
            self.db.session.commit()
        before = self.state()
        client = self.app.test_client()
        for sort in ('newest', 'oldest', 'critics_highest', 'critics_lowest', 'audience_highest', 'audience_lowest'):
            with self.subTest(sort=sort):
                response = client.get('/celebrity/fixture-actor?sort=' + sort)
                self.assertEqual(response.status_code, 200)
                items = [node for node in Document(response.get_data(as_text=True)).root.descendants('a')
                         if 'filmography-item' in node.attrs.get('class', '').split()]
                self.assertEqual(len(items), 2)
                known = next(item for item in items if item.attrs['href'] == self.MOVIE_PATH)
                self.assertIn('actor, producer', known.text())
                self.assertIn('Lead', known.text())
                if sort.startswith(('critics_', 'audience_')):
                    self.assertEqual(items[0].attrs['href'], self.MOVIE_PATH)
                self.assertEqual(self.state(), before)

    def test_invalid_and_ambiguous_query_values_fail_closed(self):
        client = self.app.test_client()
        paths = (
            '/search?search=a&search=b',
            '/browse/movies/?genre=missing',
            '/browse/movies/?certified_fresh=false',
            '/browse/movies/?rating=NC-17',
            '/browse/movies/?year=abcd',
            '/browse/movies/?year=9999',
            '/browse/movies/?platform=Missing',
            '/browse/movies/?sort=unsupported',
            '/browse/movies/?provider=unsupported',
            '/celebrity/missing?sort=unsupported',
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(client.get(path).status_code, (400, 404))

    def test_security_and_request_limits_are_explicit(self):
        self.assertNotEqual(self.app.config['SECRET_KEY'], 'rotten-tomatoes-mirror-secret-key-change-in-prod')
        self.assertEqual(self.app.config['MAX_CONTENT_LENGTH'], 64 * 1024)
        self.assertTrue(self.app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(self.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')
        client = self.app.test_client()
        token = self.csrf_token(client)
        self.assertEqual(client.post('/logout', data={'csrf_token': token}).status_code, 302)
        self.assertEqual(client.post('/register', data=b'x' * (65 * 1024),
                                     content_type='application/x-www-form-urlencoded').status_code, 413)

    def test_seeded_public_review_has_display_identity_without_account_ownership(self):
        with self.app.app_context():
            self.db.session.add(self.site.AudienceReview(
                id=2, movie_id=1, user_id=1, score=5, text='A seeded public review fixture.'))
            self.db.session.commit()
        public = self.app.test_client().get(self.MOVIE_PATH).get_data(as_text=True)
        self.assertIn('Angel G', public)
        client = self.signed_in()
        private = client.get('/user/reviews').get_data(as_text=True)
        self.assertNotIn('A seeded public review fixture.', private)
        response = self.post(client, '/user/reviews/delete/2')
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(self.db.session.get(self.site.AudienceReview, 2))

    def test_authenticated_hero_watchlist_control_posts_to_target_movie(self):
        client = self.signed_in()
        document = Document(client.get(self.MOVIE_PATH).get_data(as_text=True))
        forms = [node for node in document.root.descendants('form')
                 if node.attrs.get('class') == 'hero-watchlist-form']
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0].attrs.get('action'), self.ADD_PATH)
        self.assertEqual(forms[0].attrs.get('method'), 'POST')


if __name__ == '__main__':
    unittest.main()
