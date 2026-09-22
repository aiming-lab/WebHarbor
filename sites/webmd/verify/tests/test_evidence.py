import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence import Evidence, password_matches, state_ok
from navigation import navigation_ok


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'screenshots').mkdir()
        (self.root / 'screenshots/step_000.png').write_bytes(b'fixture')
        for name in ('initial.db', 'after.db'):
            with sqlite3.connect(self.root / name) as db:
                for table in ('users', 'articles', 'authors', 'saved_articles', 'reading_history'):
                    db.execute(f'CREATE TABLE {table} (id INTEGER)')
        self.traj = {'task_id': 'WebMD--13', 'start_url': 'http://localhost:40016/',
                     'steps': [{'url': 'http://localhost:40016/symptom-checker',
                                'page_text': 'Symptom Checker',
                                'screenshot_after': 'step_000.png'}]}
        self.write()

    def write(self):
        (self.root / 'trajectory.json').write_text(json.dumps(self.traj))

    def test_run_local_snapshots_ignore_container_environment(self):
        with patch.dict('os.environ', {'WH_CONTAINER': 'unrelated-container'}), patch('subprocess.run', side_effect=AssertionError('No Docker')):
            self.assertEqual(Evidence(self.root).initial['users'], [])

    def test_missing_snapshot_does_not_create_empty_database(self):
        (self.root / 'after.db').unlink()
        with self.assertRaises(FileNotFoundError):
            Evidence(self.root)
        self.assertFalse((self.root / 'after.db').exists())

    def test_corrupt_snapshot_fails(self):
        (self.root / 'after.db').write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):
            Evidence(self.root)

    def test_off_origin_and_path_in_query_do_not_count(self):
        for url in ('http://evil.example/symptom-checker', 'http://localhost:40016/?q=/symptom-checker'):
            self.traj['steps'][0]['url'] = url
            self.write()
            self.assertEqual(Evidence(self.root).at('/symptom-checker'), [])

    def test_missing_text_or_screenshot_cannot_prove_navigation(self):
        for field in ('page_text', 'screenshot_after'):
            saved = self.traj['steps'][0].pop(field)
            self.write()
            self.assertEqual(Evidence(self.root).pages, [])
            self.traj['steps'][0][field] = saved

    def test_indexed_dom_symptom_result(self):
        self.traj['steps'][0]['page_text'] = (
            '<h1>Possible Matches</h1> Based on your selected symptoms: '
            '<strong>Fever, Frequent urination, Painful urination</strong>. '
            'Ranked by how many of your symptoms each condition shares. '
            '[12]<a href="/condition/urinary-tract-infection">Urinary Tract Infection (UTI)</a> '
            '<span>3 of 3 symptoms match</span>')
        self.write()
        self.assertTrue(navigation_ok(Evidence(self.root), 13))

    def test_symptom_form_is_not_result(self):
        self.assertFalse(navigation_ok(Evidence(self.root), 13))

    def test_invalid_hash_and_missing_bcrypt_fail_closed(self):
        self.assertFalse(password_matches({'password_hash': 'invalid'}, 'NewPass456!'))
        with patch.dict('sys.modules', {'bcrypt': None}):
            self.assertFalse(password_matches({'password_hash': 'anything'}, 'NewPass456!'))

    def test_read_only_task_rejects_unrelated_mutation(self):
        with sqlite3.connect(self.root / 'after.db') as db:
            db.execute('INSERT INTO users VALUES (1)')
        self.assertFalse(state_ok(Evidence(self.root), 13))

if __name__ == '__main__':
    unittest.main()
