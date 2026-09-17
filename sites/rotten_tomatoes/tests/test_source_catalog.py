"""Offline source/seed regression tests in isolated copies of the real site.

Run: python -m unittest discover -s sites/rotten_tomatoes/tests -p test_source_catalog.py -v
ROTTEN_TOMATOES_SOURCE may point to a candidate site directory.
"""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


@contextmanager
def sqlite_connection(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SourceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('ROTTEN_TOMATOES_SOURCE', Path(__file__).resolve().parents[1]))
        cls.scratch = tempfile.TemporaryDirectory(prefix='rotten-source-contract-')
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.root = Path(cls.scratch.name)
        for name in ('app.py', 'seed_data.py', 'refresh_seed.py'):
            shutil.copy2(source / name, cls.root / name)
        shutil.copytree(source / 'data', cls.root / 'data')
        shutil.copytree(source / 'templates', cls.root / 'templates')
        previous_seed = sys.modules.get('seed_data')
        cls.seed = load_module('seed_data', cls.root / 'seed_data.py')
        try:
            cls.migration = load_module('_rotten_source_migration', cls.root / 'refresh_seed.py')
            cls.site = load_module('_rotten_source_app', cls.root / 'app.py')
        finally:
            if previous_seed is None:
                sys.modules.pop('seed_data', None)
            else:
                sys.modules['seed_data'] = previous_seed
        cls.addClassCleanup(sys.modules.pop, '_rotten_source_migration', None)
        cls.addClassCleanup(sys.modules.pop, '_rotten_source_app', None)
        cls.catalog_path = cls.root / 'data' / 'source_catalog.json'
        cls.catalog = cls.seed.load_catalog(cls.catalog_path)
        cls.cold_db = cls.root / 'instance' / 'rotten_tomatoes.db'
        with cls.site.app.app_context():
            cls.site.db.session.remove()
            cls.site.db.engine.dispose()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.directory = Path(self.work.name)

    def clone_cold(self, name='legacy.db'):
        target = self.directory / name
        with sqlite_connection(self.cold_db.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite_connection(target) as output:
                source.backup(output)
        return target

    def assert_catalog_projection(self, path):
        rows = self.seed.catalog_rows(self.catalog)
        with sqlite_connection(path) as connection:
            for table, expected in rows.items():
                columns = list(expected[0])
                actual = connection.execute(f'SELECT {",".join(columns)} FROM {table}').fetchall()
                expected_values = [tuple(row[key] for key in columns) for row in expected]
                self.assertEqual(sorted(actual), sorted(expected_values), table)
            self.assertEqual(connection.execute('SELECT count(*) FROM critic_reviews').fetchone()[0], 0)
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_cold_seed_is_exact_catalog_projection(self):
        self.assert_catalog_projection(self.cold_db)
        with sqlite_connection(self.cold_db) as connection:
            missing = sum(movie['audience_score'] is None for movie in self.catalog['movies'])
            self.assertGreater(missing, 0)
            self.assertEqual(connection.execute('SELECT count(*) FROM movies WHERE audience_score IS NULL').fetchone()[0], missing)
            self.assertEqual(connection.execute('SELECT count(*) FROM audience_reviews').fetchone()[0], 23)
            self.assertEqual(connection.execute('SELECT count(*) FROM users').fetchone()[0], 4)
            self.assertEqual(connection.execute('SELECT count(*) FROM watchlist_items').fetchone()[0], 16)
            self.assertEqual(connection.execute('SELECT count(*) FROM user_ratings').fetchone()[0], 12)

    def test_known_source_regressions_and_distinct_watch_semantics(self):
        movies = {movie['slug']: movie for movie in self.catalog['movies']}
        referenced = {credit['person_slug'] for movie in self.catalog['movies'] for credit in movie['credits']}
        self.assertEqual(referenced, {person['slug'] for person in self.catalog['persons']})
        self.assertEqual({credit['role'] for movie in self.catalog['movies'] for credit in movie['credits']},
                         {'actor', 'director', 'producer', 'screenwriter'})
        unknown_producer = next(person for person in self.catalog['persons']
                                if person['slug'] == 'source-credit-m82-producer-1')
        self.assertEqual(unknown_producer['name'], 'Reto Schärli')
        self.assertIsNone(unknown_producer['source_url'])
        self.assertFalse(any(person['slug'] == 'undefined' for person in self.catalog['persons']))
        self.assertEqual((movies['marty_supreme']['year'], movies['marty_supreme']['runtime_minutes']), (2025, 150))
        self.assertEqual((movies['cold_storage_2026']['year'], movies['cold_storage_2026']['runtime_minutes']), (2026, 99))
        self.assertEqual(set(movies['cold_storage_2026']['genres']), {'Horror', 'Sci-Fi', 'Comedy'})
        for movie, forbidden in [('lifehack', {'zendaya','timothee_chalamet'}),
                                 ('cold_storage_2026', {'mark_wahlberg','halle_berry'})]:
            actors = {credit['person_slug'] for credit in movies[movie]['credits'] if credit['role'] == 'actor'}
            self.assertFalse(actors & forbidden)
        self.assertEqual(movies['cold_storage_2026']['subscription_platforms'], [])
        self.assertTrue(movies['cold_storage_2026']['watch_offers'])
        with sqlite_connection(self.cold_db) as connection:
            self.assertEqual(connection.execute("SELECT streaming_platform, available_at_home FROM movies WHERE slug='cold_storage_2026'").fetchone(), ('', 1))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM persons WHERE bio<>'' OR birthplace<>'' OR birth_date<>''").fetchone()[0], 0)

    def test_existing_database_seed_validates_without_commit(self):
        before = self.migration.sha256(self.cold_db)
        with self.site.app.app_context():
            with patch.object(self.site.db.session, 'commit', side_effect=AssertionError('Committed on populated DB')):
                self.seed.seed_all(self.site.db, self.site.Genre, self.site.Movie, self.site.Person,
                                   self.site.MovieCast, self.site.CriticReview, self.site.AudienceReview,
                                   self.site.User, self.site.UserRating, self.site.WatchlistItem,
                                   self.site.ContentSnapshot)
            self.site.db.session.remove()
            self.site.db.engine.dispose()
        self.assertEqual(before, self.migration.sha256(self.cold_db))

    def test_existing_database_rejects_immutable_fact_corruption(self):
        with self.site.app.app_context():
            movie = self.site.Movie.query.filter_by(slug='war_machine').one()
            original = movie.screenwriter
            movie.screenwriter = 'Invented Writer'
            self.site.db.session.flush()
            with self.assertRaisesRegex(ValueError, 'movie fact mismatch'):
                self.seed.seed_all(self.site.db, self.site.Genre, self.site.Movie, self.site.Person,
                                   self.site.MovieCast, self.site.CriticReview, self.site.AudienceReview,
                                   self.site.User, self.site.UserRating, self.site.WatchlistItem,
                                   self.site.ContentSnapshot)
            self.site.db.session.rollback()
            movie.screenwriter = original
            self.site.db.session.rollback()

    def test_migration_preserves_state_and_rebuilds_the_same_facts(self):
        source = self.clone_cold()
        with sqlite_connection(source) as connection:
            connection.execute("UPDATE movies SET runtime_minutes=7, runtime_display='9h', synopsis='Invented placeholder', streaming_platform='Unverified Provider'")
            review = connection.execute('SELECT movie_id,user_id,score,text FROM audience_reviews WHERE id=2').fetchone()
            # Simulate the legacy schema, which allowed duplicate synthetic reviews.
            connection.execute('ALTER TABLE audience_reviews RENAME TO legacy_audience_reviews')
            connection.execute('CREATE TABLE audience_reviews(id INTEGER PRIMARY KEY,movie_id INTEGER NOT NULL,user_id INTEGER NOT NULL,score FLOAT,text TEXT,review_date DATETIME)')
            connection.execute('INSERT INTO audience_reviews SELECT * FROM legacy_audience_reviews')
            connection.execute('DROP TABLE legacy_audience_reviews')
            connection.execute('INSERT INTO audience_reviews VALUES (?,?,?,?,?,?)', (999, *review, '2000-01-01 00:00:00'))
        before = self.migration.sha256(source)
        output = self.directory / 'migrated.db'
        receipt = self.migration.migrate_copy(source, output, self.catalog_path, deduplicate=True)
        self.assertEqual(receipt['removed_review_ids'], [999])
        self.assertEqual(receipt['state_hashes_before'], receipt['state_hashes_after'])
        self.assertEqual(receipt['audience_reviews_after'], 23)
        self.assertEqual(before, self.migration.sha256(source))
        self.assert_catalog_projection(output)
        output_hash = self.migration.sha256(output)
        repeated = self.migration.migrate_copy(source, output, self.catalog_path, deduplicate=True)
        self.assertEqual(repeated['status'], 'already_migrated')
        self.assertEqual(output_hash, self.migration.sha256(output))

    def test_wrong_movie_identity_fails_without_output_or_source_changes(self):
        source = self.clone_cold()
        catalog = json.loads(self.catalog_path.read_text())
        catalog['movies'][0]['slug'] = 'different-film'
        invalid = self.directory / 'invalid.json'
        invalid.write_text(json.dumps(catalog))
        before = self.migration.sha256(source)
        output = self.directory / 'rejected.db'
        with self.assertRaisesRegex(ValueError, 'every existing movie ID and slug|official movie source URL'):
            self.migration.migrate_copy(source, output, invalid)
        self.assertFalse(output.exists())
        self.assertEqual(before, self.migration.sha256(source))

    def synthetic_addition(self):
        """Append invented test records only to an isolated catalog fixture."""
        catalog = json.loads(self.catalog_path.read_text())
        person = {
            'id': max(person['id'] for person in catalog['persons']) + 1,
            'slug': 'synthetic-incremental-producer',
            'name': 'Synthetic Incremental Producer',
            'photo_path': '', 'source_url': None,
        }
        movie = dict(catalog['movies'][0])
        movie.update(
            id=max(movie['id'] for movie in catalog['movies']) + 1,
            slug='synthetic-incremental-movie', title='Synthetic Incremental Movie',
            source={'url': 'https://www.rottentomatoes.com/m/synthetic-incremental-movie', 'sha256': '0' * 64},
            cast_source={'url': 'https://www.rottentomatoes.com/m/synthetic-incremental-movie/cast-and-crew', 'sha256': '1' * 64},
            poster_url=None, poster_sha256=None, banner_url=None, banner_sha256=None,
            synopsis='Synthetic migration fixture; not a captured movie fact.',
            runtime_minutes=91, tomatometer=None, audience_score=71,
            certified_fresh=False, genres=['Synthetic Fixture Genre'],
            directors=[], producers=[person['name']], screenwriters=[],
            watch_offers=[], watch_description='', subscription_platforms=[],
            credits=[{'person_slug': person['slug'], 'role': 'producer',
                      'character': '', 'order': 1}],
        )
        catalog['persons'].append(person)
        catalog['movies'].append(movie)
        return catalog, movie, person

    def write_fixture_catalog(self, catalog, name='synthetic-catalog.json'):
        path = self.directory / name
        path.write_text(json.dumps(catalog), encoding='utf-8')
        return path

    def test_additions_require_explicit_opt_in_and_failed_attempt_is_not_published(self):
        source = self.clone_cold()
        catalog, _, _ = self.synthetic_addition()
        catalog_path = self.write_fixture_catalog(catalog)
        output = self.directory / 'not-authorized.db'
        source_hash = self.migration.sha256(source)
        with self.assertRaisesRegex(ValueError, 'every existing movie ID and slug'):
            self.migration.migrate_copy(source, output, catalog_path)
        self.assertEqual(self.migration.sha256(source), source_hash)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + '.migration.json').exists())

    def test_explicit_addition_preserves_all_personal_rows_and_inserts_joinable_facts(self):
        source = self.clone_cold()
        # Deliberately differ from benchmark defaults to detect accidental reseeding.
        with sqlite_connection(source) as connection:
            connection.execute("UPDATE users SET name='Synthetic Preserved User' WHERE id=2")
            connection.execute("UPDATE watchlist_items SET added_at='2001-02-03 04:05:06' WHERE id=1")
            connection.execute("UPDATE user_ratings SET score=3.5, created_at='2002-03-04 05:06:07' WHERE id=1")
            connection.execute("UPDATE audience_reviews SET text='Synthetic preserved review', review_date='2003-04-05 06:07:08' WHERE id=2")
            tables = ('users', 'watchlist_items', 'user_ratings', 'audience_reviews')
            state_before = {table: connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
                            for table in tables}
            identities_before = connection.execute('SELECT id,slug,created_at FROM movies ORDER BY id').fetchall()
        source_hash = self.migration.sha256(source)
        catalog, added_movie, added_person = self.synthetic_addition()
        output = self.directory / 'added.db'
        receipt = self.migration.migrate_copy(
            source, output, self.write_fixture_catalog(catalog), allow_additions=True)
        self.assertEqual(self.migration.sha256(source), source_hash)
        self.assertTrue(receipt['allow_catalog_additions'])
        self.assertEqual(receipt['added_movie_ids'], [added_movie['id']])
        self.assertEqual(receipt['state_hashes_before'], receipt['state_hashes_after'])
        with sqlite_connection(output) as connection:
            for table in tables:
                self.assertEqual(connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall(),
                                 state_before[table], table)
            self.assertEqual(connection.execute('SELECT id,slug,created_at FROM movies WHERE id<>? ORDER BY id',
                                                (added_movie['id'],)).fetchall(), identities_before)
            self.assertEqual(connection.execute('''SELECT m.id,m.slug,m.title,m.runtime_minutes,m.runtime_display,
                                                    m.tomatometer,m.audience_score,p.slug,c.role_type,g.name
                                                    FROM movies m JOIN movie_cast c ON c.movie_id=m.id
                                                    JOIN persons p ON p.id=c.person_id
                                                    JOIN movie_genres mg ON mg.movie_id=m.id
                                                    JOIN genres g ON g.id=mg.genre_id WHERE m.id=?''',
                                                (added_movie['id'],)).fetchall(),
                             [(added_movie['id'], added_movie['slug'], added_movie['title'], 91, '1h 31m',
                               None, 71, added_person['slug'], 'producer', 'Synthetic Fixture Genre')])
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_allow_additions_still_rejects_changed_or_missing_existing_identities(self):
        source = self.clone_cold()
        source_hash = self.migration.sha256(source)
        for mutation in ('slug', 'id', 'missing', 'swapped_ids'):
            with self.subTest(mutation=mutation):
                catalog, _, _ = self.synthetic_addition()
                if mutation == 'slug':
                    catalog['movies'][0]['slug'] = 'synthetic-replaced-old-slug'
                elif mutation == 'id':
                    catalog['movies'][0]['id'] = max(movie['id'] for movie in catalog['movies']) + 1
                elif mutation == 'missing':
                    catalog['movies'].pop(0)
                    references = {credit['person_slug'] for movie in catalog['movies'] for credit in movie['credits']}
                    catalog['persons'] = [person for person in catalog['persons'] if person['slug'] in references]
                else:
                    first, second = catalog['movies'][:2]
                    first['id'], second['id'] = second['id'], first['id']
                output = self.directory / (mutation + '.db')
                with self.assertRaisesRegex(ValueError, 'every existing movie ID and slug|official movie source URL'):
                    self.migration.migrate_copy(source, output, self.write_fixture_catalog(catalog),
                                               allow_additions=True)
                self.assertEqual(self.migration.sha256(source), source_hash)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_name(output.name + '.migration.json').exists())

    def test_addition_receipt_replays_only_with_the_same_opt_in(self):
        source = self.clone_cold()
        catalog, added_movie, _ = self.synthetic_addition()
        catalog_path = self.write_fixture_catalog(catalog)
        output = self.directory / 'added.db'
        first = self.migration.migrate_copy(source, output, catalog_path, allow_additions=True)
        receipt_path = output.with_name(output.name + '.migration.json')
        output_hash, receipt_hash = self.migration.sha256(output), self.migration.sha256(receipt_path)
        repeated = self.migration.migrate_copy(source, output, catalog_path, allow_additions=True)
        self.assertEqual(repeated, {**first, 'status': 'already_migrated'})
        self.assertEqual(repeated['added_movie_ids'], [added_movie['id']])
        with self.assertRaisesRegex(ValueError, 'migration receipt'):
            self.migration.migrate_copy(source, output, catalog_path)
        self.assertEqual(self.migration.sha256(output), output_hash)
        self.assertEqual(self.migration.sha256(receipt_path), receipt_hash)

    def test_interrupted_receipt_publish_is_recovered(self):
        source = self.clone_cold()
        output = self.directory / 'recoverable.db'
        receipt = self.migration.migrate_copy(source, output, self.catalog_path)
        receipt_path = output.with_name(output.name + '.migration.json')
        pending_path = output.with_name(output.name + '.migration.pending.json')
        receipt_path.rename(pending_path)
        recovered = self.migration.migrate_copy(source, output, self.catalog_path)
        self.assertEqual(recovered, {**receipt, 'status': 'already_migrated'})
        self.assertTrue(receipt_path.is_file())
        self.assertFalse(pending_path.exists())

    def test_receipt_records_opt_in_even_when_the_catalog_has_no_additions(self):
        source = self.clone_cold()
        for allow_additions in (False, True):
            with self.subTest(allow_additions=allow_additions):
                output = self.directory / f'unchanged-{allow_additions}.db'
                first = self.migration.migrate_copy(source, output, self.catalog_path,
                                                   allow_additions=allow_additions)
                self.assertEqual(first['allow_catalog_additions'], allow_additions)
                self.assertEqual(first['added_movie_ids'], [])
                receipt_path = output.with_name(output.name + '.migration.json')
                output_hash, receipt_hash = self.migration.sha256(output), self.migration.sha256(receipt_path)
                with self.assertRaisesRegex(ValueError, 'migration receipt'):
                    self.migration.migrate_copy(source, output, self.catalog_path,
                                               allow_additions=not allow_additions)
                self.assertEqual(self.migration.sha256(output), output_hash)
                self.assertEqual(self.migration.sha256(receipt_path), receipt_hash)

    def test_command_line_addition_flag_is_required_and_reaches_migration(self):
        source = self.clone_cold()
        source_hash = self.migration.sha256(source)
        catalog, added_movie, _ = self.synthetic_addition()
        output = self.directory / 'command-line.db'
        command = [sys.executable, str(self.root / 'refresh_seed.py'), '--source', str(source),
                   '--output', str(output), '--catalog', str(self.write_fixture_catalog(catalog))]
        rejected = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('every existing movie ID and slug', rejected.stderr)
        self.assertFalse(output.exists())
        accepted = subprocess.run(command + ['--allow-catalog-additions'],
                                  capture_output=True, text=True, check=False)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        receipt = json.loads(accepted.stdout)
        self.assertTrue(receipt['allow_catalog_additions'])
        self.assertEqual(receipt['added_movie_ids'], [added_movie['id']])
        self.assertEqual(self.migration.sha256(source), source_hash)

    def test_cold_seed_content_is_queryable_without_runtime_json_files(self):
        documents = {name: json.loads((self.root / 'data' / (name + '.json')).read_text())
                     for name in self.seed.CONTENT_NAMES}
        with sqlite_connection(self.cold_db) as connection:
            stored = {name: json.loads(document) for name, document in connection.execute(
                'SELECT name,document FROM content_snapshots')}
        self.assertEqual(stored, documents)
        hidden_paths = []
        try:
            for name in self.seed.CONTENT_NAMES:
                path = self.root / 'data' / (name + '.json')
                hidden = path.with_suffix('.offline-fixture')
                path.rename(hidden)
                hidden_paths.append((path, hidden))
            with self.site.app.app_context():
                self.site.db.session.expire_all()
                for name, expected in documents.items():
                    self.assertEqual(self.site._content_document(name), expected)
            client = self.site.app.test_client()
            for route in ('/', '/browse/tv/', '/news/'):
                with self.subTest(route=route):
                    self.assertEqual(client.get(route).status_code, 200)
        finally:
            for path, hidden in hidden_paths:
                hidden.rename(path)

    def test_repeated_startup_validates_sources_and_keeps_seed_bytes(self):
        with self.site.app.app_context():
            self.site.db.session.remove()
            self.site.db.engine.dispose()
        before = self.migration.sha256(self.cold_db)
        # init_db imports seed_data again, so expose only this isolated module.
        previous_seed = sys.modules.get('seed_data')
        sys.modules['seed_data'] = self.seed
        try:
            with self.site.app.app_context():
                self.site.init_db()
                self.site.db.session.remove()
                self.site.db.engine.dispose()
        finally:
            if previous_seed is None:
                sys.modules.pop('seed_data', None)
            else:
                sys.modules['seed_data'] = previous_seed
        self.assertEqual(self.migration.sha256(self.cold_db), before)

    def test_explicit_content_migration_hashes_documents_and_rejects_drift_or_omission(self):
        source = self.clone_cold()
        source_hash = self.migration.sha256(source)
        content = self.directory / 'synthetic-content'
        shutil.copytree(self.root / 'data', content)
        homepage_path = content / 'homepage.json'
        homepage = json.loads(homepage_path.read_text())
        homepage['test_fixture_marker'] = 'Synthetic content migration fixture'
        homepage_path.write_text(json.dumps(homepage))
        output = self.directory / 'content.db'
        receipt = self.migration.migrate_copy(source, output, self.catalog_path, content_dir=content)
        self.assertEqual(receipt['content_sha256'], {
            name: self.migration.sha256(content / (name + '.json')) for name in self.seed.CONTENT_NAMES})
        with sqlite_connection(output) as connection:
            documents = {name: json.loads(document) for name, document in connection.execute(
                'SELECT name,document FROM content_snapshots')}
        self.assertEqual(documents['homepage'], homepage)
        for name in ('tv_catalog', 'feature_catalog'):
            self.assertEqual(documents[name], json.loads((content / (name + '.json')).read_text()))
        repeat = self.migration.migrate_copy(source, output, self.catalog_path, content_dir=content)
        self.assertEqual(repeat, {**receipt, 'status': 'already_migrated'})
        output_hash = self.migration.sha256(output)
        receipt_path = output.with_name(output.name + '.migration.json')
        receipt_hash = self.migration.sha256(receipt_path)
        with self.assertRaisesRegex(ValueError, 'migration receipt'):
            self.migration.migrate_copy(source, output, self.catalog_path)
        homepage['test_fixture_marker'] = 'Synthetic changed content'
        homepage_path.write_text(json.dumps(homepage))
        with self.assertRaisesRegex(ValueError, 'migration receipt'):
            self.migration.migrate_copy(source, output, self.catalog_path, content_dir=content)
        self.assertEqual(self.migration.sha256(source), source_hash)
        self.assertEqual(self.migration.sha256(output), output_hash)
        self.assertEqual(self.migration.sha256(receipt_path), receipt_hash)


if __name__ == '__main__':
    unittest.main()
