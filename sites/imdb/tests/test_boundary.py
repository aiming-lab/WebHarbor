"""Closed S1 handler regressions using only synthetic temporary database rows.

CSRF stays enabled; tokens come from the real rendered forms. These tests are
not browser task execution or S1 visual/functional acceptance.
"""
from collections import Counter
from datetime import datetime
import importlib.util
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(__file__).resolve().parents[1]
        cls.temp = tempfile.TemporaryDirectory(prefix='imdb-synthetic-boundary-tests-')
        root = Path(cls.temp.name)
        shutil.copyfile(site / 'app.py', root / 'app.py')
        (root / 'seed_data.py').write_text('def seed_all(*args):\n    pass\n')
        (root / 'templates').symlink_to(site / 'templates', target_is_directory=True)
        prior_seed = sys.modules.pop('seed_data', None)
        sys.path.insert(0, str(root))
        try:
            spec = importlib.util.spec_from_file_location('imdb_boundary_test_app', root / 'app.py')
            cls.module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.module
            spec.loader.exec_module(cls.module)
        finally:
            sys.modules.pop('seed_data', None)
            if prior_seed is not None:
                sys.modules['seed_data'] = prior_seed
            sys.path.remove(str(root))
        cls.module.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.module.app.app_context():
            cls.module.db.session.remove()
            cls.module.db.engine.dispose()
        sys.modules.pop('imdb_boundary_test_app', None)
        cls.temp.cleanup()

    def setUp(self):
        m = self.module
        with m.app.app_context():
            m.db.drop_all()
            m.db.create_all()
            now = datetime(2020, 1, 1)
            for index, name in ((1, 'Alice'), (2, 'Bob')):
                user = m.User(id=index, email=f'{name.lower()}@test.com', name=f'{name} synthetic', created_at=now)
                user.set_password('Synthetic123!')
                m.db.session.add(user)
            m.db.session.add(m.Title(id=1, tt_id='ttsynthetic', primary_title='Synthetic title',
                                    year=2000, runtime_min=120, rating_avg=7.0, num_votes=100))
            m.db.session.flush()
            for index, rating in ((1, 4), (2, 7)):
                m.db.session.add(m.UserRating(id=index, user_id=index, title_id=1,
                                            rating=rating, created_at=now))
                m.db.session.add(m.WatchlistItem(id=index, user_id=index, title_id=1, added_at=now))
            m.db.session.commit()
        self.client = m.app.test_client()

    def token(self, path='/login', client=None, base_url=None):
        response = (client or self.client).get(path, base_url=base_url)
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match, 'The rendered form must contain a CSRF token.')
        return match.group(1)

    def post(self, path, data=None, form_path=None, base_url=None, **kwargs):
        data = dict(data or {})
        data['csrf_token'] = self.token(form_path or path, base_url=base_url)
        return self.client.post(path, data=data, base_url=base_url, **kwargs)

    def login(self, base_url=None):
        response = self.post('/login', {'email': 'alice@test.com', 'password': 'Synthetic123!'}, base_url=base_url)
        self.assertEqual(response.status_code, 302)

    def actor(self, base_url=None):
        with self.client.session_transaction(base_url=base_url) as session:
            return session.get('_user_id')

    def test_home_and_news_sort_by_publication_date_and_filter_category(self):
        m = self.module
        with m.app.app_context():
            m.db.session.add_all([
                m.NewsItem(id=1, headline='Newest film news', published_at='2025-02-14', category='Movies'),
                m.NewsItem(id=9, headline='Old television news', published_at='2024-01-01', category='TV'),
            ])
            m.db.session.commit()
        for path in ('/', '/news'):
            body = self.client.get(path).get_data(as_text=True)
            self.assertLess(body.index('Newest film news'), body.index('Old television news'))
        response = self.client.get('/news?category=Movies')
        self.assertIn(b'Newest film news', response.data)
        self.assertNotIn(b'Old television news', response.data)
        self.assertEqual(self.client.get('/news/1').status_code, 200)
        self.assertEqual(self.client.get('/news/999').status_code, 404)

    def test_recently_viewed_is_session_local_and_clear_requires_csrf(self):
        self.assertEqual(self.client.get('/title/ttsynthetic').status_code, 200)
        with self.client.session_transaction() as state:
            self.assertEqual(state['recent_titles'], ['ttsynthetic'])
        self.client.get('/title/ttsynthetic')
        with self.client.session_transaction() as state:
            self.assertEqual(state['recent_titles'], ['ttsynthetic'])
        other = self.module.app.test_client()
        self.assertIn(b'You have no recently viewed pages', other.get('/').data)
        self.assertEqual(self.client.post('/recently-viewed/clear').status_code, 400)
        self.assertEqual(self.client.get('/recently-viewed/clear').status_code, 405)
        response = self.client.post('/recently-viewed/clear', data={'csrf_token': self.token('/')})
        self.assertEqual(response.status_code, 302)
        self.assertIn(b'You have no recently viewed pages', self.client.get('/').data)

    def test_home_cards_use_authenticated_watchlist_state(self):
        m = self.module
        with m.app.app_context():
            title = m.db.session.get(m.Title, 1)
            title.top_rank = 1
            m.db.session.commit()
        self.assertIn(b'Sign in to add Synthetic title', self.client.get('/').data)
        self.login()
        body = self.client.get('/').data
        self.assertIn(b'Remove Synthetic title from Watchlist', body)
        self.assertIn(b'In Watchlist', body)
        response = self.client.post('/title/ttsynthetic/watchlist', data={'csrf_token': self.token('/')},
                                    headers={'Referer': 'http://localhost/'})
        self.assertEqual(response.location, '/')
        self.assertIn(b'Add Synthetic title to Watchlist', self.client.get('/').data)

    def test_home_feature_escapes_source_text_and_unknown_features_404(self):
        m = self.module
        with m.app.app_context():
            m.db.session.add(m.HomeFeature(id='synthetic', kind='topic', position=1,
                heading='<script>alert(1)</script>', subtitle='Source description',
                source_url='https://www.imdb.com/example/', captured_at='2026-09-10',
                payload={}))
            m.db.session.commit()
        for path in ('/', '/feature/synthetic'):
            body = self.client.get(path).data
            self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;', body)
            self.assertNotIn(b'<script>alert(1)</script>', body)
        self.assertEqual(self.client.get('/feature/missing').status_code, 404)

    def snapshot(self):
        # Rows, including password hashes, are compared in memory, never logged.
        with self.module.app.app_context():
            return {table.name: Counter(tuple(row) for row in self.module.db.session.execute(table.select()))
                    for table in self.module.db.metadata.sorted_tables}

    def test_snapshot_collections_are_dated_local_and_do_not_invent_missing_facts(self):
        m = self.module
        with m.app.app_context():
            for kind, payload in [('streaming', {'source_id': 'ttsynthetic', 'service': 'PRIME VIDEO', 'rating': '8.0'}),
                                  ('starmeter', {'source_id': 'nm1', 'rank': 7, 'known_for': ['Source film']}),
                                  ('birthday', {'source_id': 'nm1'}),
                                  ('tv_schedule', {'source_id': 'tt2', 'episode': 'New: Season 1', 'air_date': 'Wed, Sep 16'})]:
                m.db.session.add(m.HomeFeature(id=kind + '-test', kind=kind, position=1,
                    heading='Source ' + kind, subtitle='Source data', image_path='images/test.jpg',
                    poster_path='images/test.jpg', source_url='https://www.imdb.com/',
                    captured_at='2026-09-10', payload=payload))
            m.db.session.commit()
        for kind in ('streaming', 'birthday', 'tv_schedule', 'starmeter'):
            for path in ('/discover/' + kind, '/feature/' + kind + '-test'):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'2026-09-10', response.data)
                self.assertIn(('Source ' + kind).encode(), response.data)
        detail = self.client.get('/feature/streaming-test').data
        self.assertIn(b'/title/ttsynthetic', detail)
        self.assertIn(b'not available in this offline mirror', detail)
        self.assertNotIn(b'Age at capture', self.client.get('/feature/birthday-test').data)
        chart_detail = self.client.get('/feature/starmeter-test').data
        self.assertIn(b'STARmeter rank at capture</dt><dd>7</dd>', chart_detail)
        self.assertIn(b'Source film', chart_detail)
        self.assertNotIn(b'Add to favorite', chart_detail)
        self.assertIn(b'person-rank">7</span>', self.client.get('/').data)
        self.assertNotIn(b'IMDb rating at capture', self.client.get('/feature/tv_schedule-test').data)
        self.assertEqual(self.client.get('/discover/unknown').status_code, 404)

    def test_home_release_and_favorite_ordering_use_real_fields(self):
        m = self.module
        with m.app.app_context():
            title = m.db.session.get(m.Title, 1)
            title.release_date = '2025-02-01'
            m.db.session.add(m.Title(id=2, tt_id='ttsecond', primary_title='Second release',
                release_date='2025-01-01', num_votes=1000, rating_avg=9.0))
            m.db.session.add(m.Title(id=3, tt_id='ttinvalid', primary_title='Unparsed release',
                release_date='Release date | 2027', num_votes=1, rating_avg=8.0))
            m.db.session.commit()
        body = self.client.get('/').get_data(as_text=True)
        releases = body.split('Latest catalog releases', 1)[1].split('</section>', 1)[0]
        self.assertLess(releases.index('Synthetic title'), releases.index('Second release'))
        self.assertNotIn('Unparsed release', releases)
        favorites = body.split('Fan favorites', 1)[1].split('</section>', 1)[0]
        self.assertLess(favorites.index('Second release'), favorites.index('Synthetic title'))

    def assert_unchanged(self, before):
        after = self.snapshot()
        self.assertEqual([name for name in before if before[name] != after[name]], [])

    def test_all_post_routes_reject_missing_and_invalid_csrf(self):
        targets = ['/login', '/register', '/title/ttsynthetic/rate',
                   '/title/ttsynthetic/review', '/title/ttsynthetic/watchlist', '/logout']
        self.login()
        for target in targets:
            for supplied in ({}, {'csrf_token': 'invalid'}):
                with self.subTest(target=target, supplied=bool(supplied)):
                    before = self.snapshot()
                    response = self.client.post(target, data={
                        'email': 'new@test.com', 'name': 'New', 'password': 'Synthetic123!',
                        'rating': '8', 'headline': 'Synthetic review', 'body': 'Synthetic body.', **supplied})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(b'CSRF', response.data)
                    self.assertEqual(self.actor(), '1')
                    self.assert_unchanged(before)

    def test_login_and_registration_without_session_reject_missing_csrf(self):
        for target in ('/login', '/register'):
            before = self.snapshot()
            response = self.client.post(target, data={'email': 'new@test.com', 'name': 'New',
                                                      'password': 'Synthetic123!'})
            self.assertEqual(response.status_code, 400)
            self.assertIsNone(self.actor())
            self.assert_unchanged(before)

    def test_other_session_token_is_rejected(self):
        other = self.module.app.test_client()
        other_token = self.token(client=other)
        self.login()
        before = self.snapshot()
        response = self.client.post('/title/ttsynthetic/rate', data={'rating': '8', 'csrf_token': other_token})
        self.assertEqual(response.status_code, 400)
        self.assert_unchanged(before)

    def test_token_expiry_remains_enabled(self):
        # Only age the GET-issued signatures: the session remains within its
        # lifetime while the form token exceeds Flask-WTF's unchanged limit.
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=int(time.time()) - 7200):
            token = self.token()
        before = self.snapshot()
        response = self.client.post('/login', data={'email': 'alice@test.com',
                                    'password': 'Synthetic123!', 'csrf_token': token})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'expired', response.data)
        self.assertIsNone(self.actor())
        self.assert_unchanged(before)

    def test_cross_origin_without_token_cannot_mutate(self):
        base = 'http://localhost:48015'
        self.login(base_url=base)
        for action in ('rate', 'review', 'watchlist'):
            before = self.snapshot()
            response = self.client.post('/title/ttsynthetic/' + action, base_url=base,
                                        headers={'Origin': 'http://localhost:48016',
                                                 'Referer': 'http://localhost:48016/form'},
                                        data={'rating': '8', 'headline': 'Synthetic', 'body': 'Body'})
            self.assertEqual(response.status_code, 400)
            self.assert_unchanged(before)

    def test_real_form_tokens_allow_normal_writes_and_preserve_ownership(self):
        self.login()
        m = self.module
        with m.app.app_context():
            old = m.UserRating.query.filter_by(user_id=1).one()
            identity = old.id, old.created_at
        response = self.post('/title/ttsynthetic/rate', {'rating': '8', 'user_id': '2'},
                             form_path='/title/ttsynthetic')
        self.assertEqual(response.status_code, 302)
        with m.app.app_context():
            old = m.UserRating.query.filter_by(user_id=1).one()
            self.assertEqual((old.id, old.created_at), identity)
            self.assertEqual(old.rating, 8)
            self.assertEqual(m.UserRating.query.filter_by(user_id=2).one().rating, 7)
        response = self.post('/title/ttsynthetic/review', {'headline': 'Synthetic review', 'body': 'Body.',
                             'rating': '10', 'user_id': '2', 'helpful_count': '999', 'is_seed': '1'})
        self.assertEqual(response.status_code, 302)
        with m.app.app_context():
            row = m.Review.query.one()
            self.assertEqual((row.user_id, row.title_id, row.rating, row.helpful_count, row.is_seed), (1, 1, 10, 0, False))
        response = self.post('/title/ttsynthetic/watchlist', {'user_id': '2'}, form_path='/list/watchlist')
        self.assertEqual(response.status_code, 302)
        with m.app.app_context():
            self.assertEqual(m.WatchlistItem.query.filter_by(user_id=1).count(), 0)
            self.assertEqual(m.WatchlistItem.query.filter_by(user_id=2).count(), 1)
        response = self.post('/title/ttsynthetic/watchlist', form_path='/title/ttsynthetic')
        self.assertEqual(response.status_code, 302)
        with m.app.app_context():
            self.assertEqual(m.WatchlistItem.query.filter_by(user_id=1).count(), 1)

    def test_logout_requires_token_post_and_get_head_preserve_session(self):
        self.login()
        before = self.snapshot()
        for method in ('GET', 'HEAD'):
            response = self.client.open('/logout', method=method)
            self.assertEqual(response.status_code, 405)
            self.assertEqual(self.actor(), '1')
        response = self.post('/logout', form_path='/account')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.actor())
        self.assert_unchanged(before)

    def test_account_body_logout_form_ends_session_without_data_changes(self):
        self.login()
        before = self.snapshot()
        page = self.client.get('/account').get_data(as_text=True)
        self.assertNotRegex(page, r'<a\b[^>]*href="/logout"')
        forms = [(attributes, body) for attributes, body in
                 re.findall(r'<form\b([^>]*)>(.*?)</form>', page, re.S)
                 if 'action="/logout"' in attributes]
        self.assertEqual(len(forms), 2, 'Both navigation and account-body exits must submit forms.')
        attributes, body = forms[-1]
        self.assertIn('method="post"', attributes)
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
        self.assertIsNotNone(token)
        response = self.client.post('/logout', data={'csrf_token': token.group(1)})
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.actor())
        self.assert_unchanged(before)

    def test_watchlist_referrers_preserve_only_same_origin_path_query(self):
        base = 'http://localhost:48015'
        self.login(base_url=base)
        cases = [
            (base + '/list/watchlist?sort=recent#ignored', '/list/watchlist?sort=recent'),
            ('http://LOCALHOST:48015/list/watchlist', '/list/watchlist'),
            ('http://localhost:48015', '/'),
            ('http://localhost:48016/list/watchlist', '/title/ttsynthetic'),
            ('https://localhost:48015/list/watchlist', '/title/ttsynthetic'),
            ('https://example.invalid/landing', '/title/ttsynthetic'),
            ('//example.invalid/landing', '/title/ttsynthetic'),
            ('//localhost:48015/list/watchlist', '/title/ttsynthetic'),
            ('http://alice@localhost:48015/list/watchlist', '/title/ttsynthetic'),
            ('http://localhost:48015@evil.invalid/landing', '/title/ttsynthetic'),
            ('http://localhost:invalid/landing', '/title/ttsynthetic'),
            ('http://localhost:99999/landing', '/title/ttsynthetic'),
            ('http://localhost:48015\\@evil.invalid/landing', '/title/ttsynthetic'),
            ('http://localhost:48015/\\evil.invalid/landing', '/title/ttsynthetic'),
            ('http://localhost:48015//evil.invalid/landing', '/title/ttsynthetic'),
            ('http://localhost:48015/%2f%2fevil.invalid', '/title/ttsynthetic'),
            ('http://localhost:48015/%5cevil.invalid', '/title/ttsynthetic'),
            ('http://localhost:48015/list/%09watchlist', '/title/ttsynthetic'),
            ('http://localhost:48015/list/\twatchlist', '/title/ttsynthetic'),
        ]
        for referrer, expected in cases:
            with self.subTest(referrer=repr(referrer)):
                response = self.post('/title/ttsynthetic/watchlist', form_path='/title/ttsynthetic', base_url=base,
                                     headers={'Referer': referrer})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, expected)

    def test_referrer_default_ports_and_local_ipv6_are_parsed(self):
        for base, referrer, expected in (
                ('http://localhost', 'http://localhost:80/list/watchlist?q=1', '/list/watchlist?q=1'),
                ('http://localhost:80', 'http://localhost/list/watchlist', '/list/watchlist'),
                ('http://[::1]:48015', 'http://[::1]:48015/list/watchlist', '/list/watchlist'),
                ('http://task.localhost:48015', 'http://task.localhost:48015/list/watchlist', '/list/watchlist')):
            self.client = self.module.app.test_client()
            self.login(base_url=base)
            response = self.post('/title/ttsynthetic/watchlist', form_path='/title/ttsynthetic', base_url=base,
                                 headers={'Referer': referrer})
            self.assertEqual(response.location, expected)

    def test_invalid_years_return_clear_400_without_database_changes(self):
        before = self.snapshot()
        for key in ('year_from', 'year_to'):
            for value in ('9223372036854775808', '-9223372036854775809', '0', '10000', 'nonsense', '2.5'):
                with self.subTest(key=key, value=value):
                    response = self.client.get('/search/title', query_string={key: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(b'year', response.data.lower())
                    self.assert_unchanged(before)

    def test_blank_and_supported_years_preserve_search(self):
        before = self.snapshot()
        for query in ({}, {'year_from': '', 'year_to': ' '}, {'year_from': '1', 'year_to': '9999'},
                      {'year_from': '2000', 'year_to': '2000'}):
            response = self.client.get('/search/title', query_string=query)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Synthetic title', response.data)
        response = self.client.get('/search/title', query_string={'year_from': '2001'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'Synthetic title', response.data)
        self.assert_unchanged(before)

    def test_registration_email_validation_is_offline_and_normalized(self):
        for value in ('not-an-email', 'a@@test.com', 'a b@test.com'):
            before = self.snapshot()
            response = self.post('/register', {'email': value, 'name': 'New', 'password': 'Synthetic123!'})
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'valid email', response.data)
            self.assertIsNone(self.actor())
            self.assert_unchanged(before)
        # Any unintended DNS/network lookup must fail this synthetic test.
        with (patch('socket.getaddrinfo', side_effect=AssertionError('No network allowed')),
              patch('dns.resolver.Resolver.resolve', side_effect=AssertionError('No DNS allowed'))):
            response = self.post('/register', {'email': '  NEW@TEST.COM  ', 'name': ' New ',
                                              'password': 'Synthetic123!'})
        self.assertEqual(response.status_code, 302)
        with self.module.app.app_context():
            row = self.module.User.query.filter_by(email='new@test.com').one()
            self.assertEqual(row.name, 'New')
            new_id = str(row.id)
        self.assertEqual(self.actor(), new_id)

    def test_duplicate_registration_and_bad_login_remain_rejected(self):
        before = self.snapshot()
        response = self.post('/register', {'email': ' ALICE@TEST.COM ', 'name': 'Duplicate',
                                          'password': 'Synthetic123!'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'already exists', response.data)
        response = self.post('/login', {'email': 'alice@test.com', 'password': 'bad'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.actor())
        self.assert_unchanged(before)


if __name__ == '__main__':
    unittest.main()
