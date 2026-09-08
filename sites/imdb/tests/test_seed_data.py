import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migrate_seed import migrate_seed
from seed_data import _ld_nm_id, _parse_release_date, _release_date_from_scrape
import seed_data


class SourceParsingTests(unittest.TestCase):
    def test_seed_rejects_wrong_missing_and_malformed_person_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            scraped = Path(directory)
            for nm_id, url in (
                    ('nm1165110', 'https://www.imdb.com/name/nm1165110/'),
                    ('nm0000245', 'https://www.imdb.com/name/nm1165110/'),
                    ('nm0000001', ''),
                    ('nm0000002', 'https://www.imdb.com/name/nm0000002wrong/')):
                (scraped / f'name_{nm_id}.json').write_text(json.dumps(
                    {'h1': 'Chris Hemsworth', 'ld': {'url': url}}))
            database = Mock()
            database.session.query.return_value.count.return_value = 0
            person = Mock(side_effect=lambda **values: SimpleNamespace(**values, credits=[]))
            models = [Mock() for _ in range(8)]
            with patch.object(seed_data, 'SCRAPED', scraped), patch('builtins.print'):
                seed_data.seed_all(database, models[0], person, *models[1:])
            self.assertEqual(person.call_count, 1)
            self.assertEqual(person.call_args.kwargs['nm_id'], 'nm1165110')

    def test_person_canonical_url_is_an_exact_identity(self):
        self.assertEqual(_ld_nm_id({'url': 'https://www.imdb.com/name/nm1165110/'}), 'nm1165110')
        self.assertNotEqual(_ld_nm_id({'url': 'https://www.imdb.com/name/nm0000245/'}), 'nm1165110')
        for url in ('', '/title/tt1165110/', '/name/nm1165110garbage/', 42):
            with self.subTest(url=url):
                self.assertIsNone(_ld_nm_id({'url': url}))
        self.assertIsNone(_ld_nm_id({}))

    def test_complete_dates_only_and_structured_source_wins(self):
        self.assertEqual(_parse_release_date('2008-07-18'), '2008-07-18')
        self.assertEqual(_parse_release_date('Release date | July 18, 2008 (United States)'), '2008-07-18')
        self.assertEqual(_parse_release_date('September 1, 2000 (Italy)'), '2000-09-01')
        self.assertEqual(_release_date_from_scrape(
            {'datePublished': '2008-07-14'}, {'releasedate': 'July 18, 2008 (United States)'}), '2008-07-14')
        self.assertEqual(_release_date_from_scrape(
            {'datePublished': '2008-02-30'}, {'releaseDate': 'July 18, 2008'}), '2008-07-18')
        for value in ('2008', '2008-07', 'Release date | July 18, 20',
                      'Release date | February 30, 2008', '2008-07-180', 'Unknown'):
            with self.subTest(value=value):
                self.assertEqual(_parse_release_date(value), '')


class SeedMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / 'imdb.db'
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript('''
                CREATE TABLE persons (id INTEGER PRIMARY KEY, nm_id TEXT UNIQUE,
                    name TEXT, birth_year INTEGER, death_year INTEGER,
                    birth_place TEXT, bio TEXT, primary_profession TEXT,
                    photo_path TEXT, known_for_json TEXT);
                CREATE TABLE titles (id INTEGER PRIMARY KEY, tt_id TEXT,
                    primary_title TEXT, release_date TEXT, rating_avg REAL);
                CREATE TABLE credits (id INTEGER PRIMARY KEY, title_id INTEGER,
                    person_id INTEGER, character TEXT);
                CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE user_ratings (id INTEGER PRIMARY KEY, user_id INTEGER,
                    title_id INTEGER, rating INTEGER);
                INSERT INTO persons VALUES (1, 'nm1165110', 'Robin Williams', 1951, 2014,
                    'unverified place', 'unverified biography', 'Actor', 'nm1165110.jpg', '["tt0000001"]');
                INSERT INTO persons VALUES (2, 'nm0850696', 'Matt Tarses', 1966, NULL,
                    '', 'retain biography', 'Producer', 'retain.jpg', '[]');
                INSERT INTO persons VALUES (3, 'nm0001855', 'Tom Wilson(LXXXVI)', NULL, NULL,
                    '', 'retain variant', 'Actor', 'variant.jpg', '[]');
                INSERT INTO titles VALUES (1, 'tt4154796', 'Avengers: Endgame',
                    'Release date | April 26, 2019 (United States)', 8.4);
                INSERT INTO titles VALUES (2, 'tt0000002', 'Partial source', 'Release date | May 2, 20', 5.0);
                INSERT INTO credits VALUES (1, 1, 1, 'Thor');
                INSERT INTO users VALUES (1, 'seed user');
                INSERT INTO user_ratings VALUES (1, 1, 1, 8);
            ''')
        self.manifest = Path(self.temp.name) / 'corrections.json'
        self.manifest.write_text(json.dumps({
            'schema_version': 1,
            'source_seed': {'sha256': hashlib.sha256(self.db_path.read_bytes()).hexdigest()},
            'people': [{'nconst': 'nm1165110', 'primaryName': 'Chris Hemsworth',
                        'birthYear': '1983', 'deathYear': '\\N',
                        'primaryProfession': 'actor,producer,soundtrack',
                        'knownForTitles': 'tt4154796,tt0800369',
                        'kind': 'profile_collision'}],
            'birth_year_corrections': [{'nconst': 'nm0850696', 'birthYear': '1968'}],
        }))

    def rows(self, table):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()

    def test_migration_preserves_relationships_and_unrelated_state(self):
        protected = {table: self.rows(table) for table in ('credits', 'users', 'user_ratings')}
        old_people = self.rows('persons')
        old_titles = self.rows('titles')
        result = migrate_seed(self.db_path, self.manifest)
        for table, rows in protected.items():
            self.assertEqual(self.rows(table), rows)
        people = self.rows('persons')
        self.assertEqual(people[0], (1, 'nm1165110', 'Chris Hemsworth', 1983, None,
                                    '', '', 'Actor, Producer, Soundtrack', '',
                                    '["tt4154796", "tt0800369"]'))
        self.assertEqual(people[1], old_people[1][:3] + (1968,) + old_people[1][4:])
        self.assertEqual(people[2], old_people[2])
        self.assertEqual(self.rows('titles')[0], old_titles[0][:3] + ('2019-04-26',) + old_titles[0][4:])
        self.assertEqual(self.rows('titles')[1], old_titles[1])
        self.assertEqual(result['changed_rows'], {'persons': 2, 'titles': 1})
        self.assertEqual(result['protected_tables_unchanged'], ['credits', 'user_ratings', 'users'])

    def test_second_migration_is_byte_identical(self):
        migrate_seed(self.db_path, self.manifest)
        before = self.db_path.read_bytes()
        result = migrate_seed(self.db_path, self.manifest)
        self.assertEqual(result['changed_rows'], {})
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_unexpected_source_is_rejected_without_writes(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("UPDATE users SET name='different state'")
        before = self.db_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'source seed'):
            migrate_seed(self.db_path, self.manifest)
        self.assertEqual(self.db_path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
