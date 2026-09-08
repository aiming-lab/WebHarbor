"""Handler regressions against a disposable copy of the packaged seed.

Run with the Dockerfile dependencies: python sites/imdb/tests/test_app.py
These tests do not replace browser task execution or visual acceptance.
"""
import importlib.util
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


class ReviewInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(__file__).resolve().parents[1]
        cls.temp = tempfile.TemporaryDirectory(prefix='imdb-handler-tests-')
        root = Path(cls.temp.name)
        for filename in ('app.py', 'seed_data.py'):
            shutil.copyfile(site / filename, root / filename)
        (root / 'templates').symlink_to(site / 'templates', target_is_directory=True)
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
