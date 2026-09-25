import hashlib
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE / 'verify'))
from answers import answer_ok
from verify_lib import evaluate, navigate_check
from state import password_matches


class AnswerContracts(unittest.TestCase):
    def test_positive_equivalents(self):
        cases = [
            (0, 'Yosemite Creek Campground; Hiking.'),
            (0, 'Yosemite Creek is open; Porcupine Flat is not. Waterfalls.'),
            (1, 'An oak-shaded campsite; another campsite overlooking the ocean.'),
            (1, 'A large tree at a campsite and a picnic table with a bear box.'),
            (2, 'Inyo National Forest Wilderness Permits — parent: Inyo National Forest.'),
            (3, 'SF Maritime highlights Historic Ships; Fort Point is part of Golden Gate National Recreation Area.'),
            (3, 'Historic Ships: SF Maritime. Golden Gate: Fort Point.'),
            (4, 'Hemlock Cabin.'),
            (5, 'Kayaking. It is a permit, not a campground.'),
            (6, 'Ticket reservations.'),
            (7, 'Check the type of reservation needed, permitted travel dates, and the managing authority’s rules.'),
            (7, 'Inventory type; allowed date window; agency rules.'),
            (8, 'Fort Point, Yosemite, and Denali.'),
            (9, 'Yosemite. Denali does not have the additional fee note.'),
            (10, 'Voyageurs National Park Tours; parent area: Voyageurs National Park.'),
            (17, 'Georgia (GA); Beach Camping.'),
            (18, 'Hiking; both.'),
            (18, 'Wildlife Viewing. Day Use Permit and Overnight Permit.'),
        ]
        for task, answer in cases:
            with self.subTest(task=task, answer=answer):
                self.assertTrue(answer_ok(task, answer))

    def test_targeted_wrong_answers(self):
        cases = [
            (0, 'Yosemite Creek is closed. Porcupine Flat is open and offers Hiking.'),
            (1, 'A campsite.'), (1, 'A picnic table and a bear box.'),
            (2, 'Inyo National Forest Wilderness Permits is in Yosemite National Park.'),
            (3, 'Fort Point highlights Historic Ships. SF Maritime is part of Golden Gate.'),
            (4, 'It is not Hemlock Cabin.'),
            (5, 'Kayaking. It is a campground, not a permit.'),
            (6, 'Campground reservations include the fee; tickets do not.'),
            (7, 'Inventory prices, date of birth, and the advertising agency logo.'),
            (8, 'The article does not mention Fort Point, Yosemite or Denali.'),
            (9, 'Denali has the extra fee, but Yosemite does not.'),
            (10, 'Voyageurs National Park Tours is part of Yellowstone National Park.'),
            (17, 'Florida, not Georgia. Beach Camping.'),
            (18, 'Hiking; only Day Use Permit, not Overnight Permit.'),
        ]
        for task, answer in cases:
            with self.subTest(task=task, answer=answer):
                self.assertFalse(answer_ok(task, answer))

    def test_empty_answers(self):
        for task in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18):
            self.assertFalse(answer_ok(task, ''))


class EvidenceContracts(unittest.TestCase):
    def test_navigation_origin_and_workflow(self):
        def run(urls):
            return {'start_url': 'http://localhost:40035/', 'steps': [{'url': u} for u in urls]}
        self.assertTrue(navigate_check(4, run(['http://localhost:40035/search?q=Alaska', 'http://localhost:40035/facility/hemlock-cabin'])))
        for urls in ([
            'http://unrelated.example/search?q=Alaska', 'http://unrelated.example/facility/hemlock-cabin'],
            ['http://localhost:40035/?q=hemlock-cabin'],
            ['http://localhost:40035/facility/hemlock-cabin']):
            with self.assertRaises(ValueError):
                navigate_check(4, run(urls))

    def test_missing_evidence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(evaluate(0, tmp)['pass'])

    def test_password(self):
        salt = 'test-only'
        digest = hashlib.pbkdf2_hmac('sha256', b'TrailPass2026', salt.encode(), 100000).hex()
        stored = f'pbkdf2:sha256:100000${salt}${digest}'
        self.assertTrue(password_matches(stored, 'TrailPass2026'))
        self.assertFalse(password_matches(stored, 'wrong'))
        self.assertFalse(password_matches('invalid', 'TrailPass2026'))

    def test_migration_noop_and_anonymous_ownership(self):
        spec = importlib.util.spec_from_file_location('recreation_migrate', SITE / 'migrate_seed.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'seed.db'
            with sqlite3.connect(path) as con:
                con.execute('CREATE TABLE user (id INTEGER PRIMARY KEY)')
                con.execute('CREATE TABLE review (id INTEGER PRIMARY KEY, author TEXT)')
                con.execute("INSERT INTO review VALUES (1, 'David Kim')")
            self.assertTrue(module.migrate(path))
            first = path.read_bytes()
            self.assertFalse(module.migrate(path))
            self.assertEqual(first, path.read_bytes())
            with sqlite3.connect(path) as con:
                self.assertIsNone(con.execute('SELECT user_id FROM review').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
