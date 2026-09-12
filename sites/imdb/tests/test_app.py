"""Handler regressions against a disposable copy of the packaged seed.

Run with the Dockerfile dependencies: python sites/imdb/tests/test_app.py
These tests do not replace browser task execution or visual acceptance.
"""
import importlib.util
from html import unescape
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from urllib.parse import urlsplit


class ReviewInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(__file__).resolve().parents[1]
        cls.temp = tempfile.TemporaryDirectory(prefix='imdb-handler-tests-')
        root = Path(cls.temp.name)
        for filename in ('app.py', 'seed_data.py'):
            shutil.copyfile(site / filename, root / filename)
        (root / 'templates').symlink_to(site / 'templates', target_is_directory=True)
        (root / 'static').symlink_to(site / 'static', target_is_directory=True)
        (root / 'instance').mkdir()
        shutil.copyfile(site / 'instance_seed/imdb.db', root / 'instance/imdb.db')
        sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location('imdb_test_app', root / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.module.app.app_context():
            cls.module.db.session.remove()
            cls.module.db.engine.dispose()
        sys.path.remove(cls.temp.name)
        sys.modules.pop('imdb_test_app', None)
        cls.temp.cleanup()

    def setUp(self):
        self.client = self.module.app.test_client()
        response = self.client.post('/login', data={
            'email': 'alice.j@test.com', 'password': 'TestPass123!',
            'csrf_token': self.csrf_token('/login'),
        })
        self.assertEqual(response.status_code, 302)

    def csrf_token(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match, 'The rendered form must contain a CSRF token.')
        return match.group(1)

    def review_count(self):
        with self.module.app.app_context():
            return self.module.Review.query.count()

    def test_homepage_links_and_media_are_local_and_resolve(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        targets = set(unescape(value) for value in re.findall(r'(?:href|src)="([^"]+)"', body))
        for target in sorted(targets):
            with self.subTest(target=target):
                self.assertFalse(urlsplit(target).netloc, 'Homepage must not hotlink external assets or routes')
                if target.startswith('/'):
                    with self.client.get(target, follow_redirects=True) as result:
                        self.assertEqual(result.status_code, 200)

    def test_featured_today_recreates_the_full_sourced_editorial_path(self):
        response = self.client.get('/feature/featured-today-1')
        self.assertEqual(response.status_code, 200)
        body = unescape(response.get_data(as_text=True))
        self.assertIn('Here\'s what to watch in September', body)
        self.assertIn('17 titles', body)
        self.assertEqual(body.count('data-anticipated-item'), 17)
        for expected in ('Hopeu', 'Practical Magic 2', 'Lanterns', 'MobLand',
                         'Victorian Psycho'):
            self.assertIn(expected, body)
        targets = set(unescape(value) for value in re.findall(r'(?:href|src)="([^"]+)"', body))
        for target in sorted(targets):
            with self.subTest(target=target):
                self.assertFalse(urlsplit(target).netloc,
                                 'The editorial page must not hotlink external assets or routes')

    def test_featured_today_items_have_local_detail_routes(self):
        response = self.client.get('/feature/featured-today-1')
        item_paths = sorted(set(re.findall(
            r'href="(/feature/featured-today-1/title/tt\d+)"',
            response.get_data(as_text=True))))
        self.assertEqual(len(item_paths), 17)
        for path in item_paths:
            with self.subTest(path=path):
                detail = self.client.get(path)
                self.assertEqual(detail.status_code, 200)
                self.assertIn(b'Back to all 17 titles', detail.data)
        self.assertEqual(
            self.client.get('/feature/featured-today-1/title/tt0000000').status_code,
            404,
        )

    def test_bootstrap_on_populated_seed_preserves_database_bytes(self):
        database = Path(self.temp.name) / 'instance/imdb.db'
        before = database.read_bytes()
        self.module._bootstrap()
        self.assertEqual(database.read_bytes(), before)

    def test_invalid_review_ratings_do_not_write(self):
        for rating in ('nonsense', '0', '11', '2.5'):
            with self.subTest(rating=rating):
                before = self.review_count()
                response = self.client.post('/title/tt0816692/review', data={
                    'headline': 'Validation probe', 'body': 'A non-empty review.',
                    'rating': rating,
                    'csrf_token': self.csrf_token('/title/tt0816692/review'),
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Rating must be a whole number from 1 to 10.', response.data)
                self.assertEqual(self.review_count(), before)

    def test_valid_optional_and_boundary_review_ratings(self):
        for rating in ('', '1', '10'):
            with self.subTest(rating=rating):
                before = self.review_count()
                response = self.client.post('/title/tt0816692/review', data={
                    'headline': 'Valid rating probe', 'body': 'A non-empty review.',
                    'rating': rating,
                    'csrf_token': self.csrf_token('/title/tt0816692/review'),
                })
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.review_count(), before + 1)
                with self.module.app.app_context():
                    row = self.module.Review.query.order_by(self.module.Review.id.desc()).first()
                    self.assertEqual(row.rating, int(rating) if rating else None)


if __name__ == '__main__':
    unittest.main()
