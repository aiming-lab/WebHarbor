"""Regression tests use a private copy; never mutate the shipped seed/runtime."""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SITE = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.site = Path(self.temp.name) / 'cookpad'
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns(
            'instance', '__pycache__', 'tests', 'static', 'verify'))
        self.seed = self.site / 'instance_seed/cookpad.db'
        self.runtime = self.site / 'instance/cookpad.db'

    def tearDown(self):
        self.temp.cleanup()

    def start(self):
        env = {key: value for key, value in os.environ.items()
               if key not in {'COOKPAD_DATABASE', 'COOKPAD_SEED_BUILD'}}
        return subprocess.run([sys.executable, '-c', 'import app'], cwd=self.site,
                              capture_output=True, text=True, env=env)

    def test_restore_is_byte_identical_and_second_start_is_noop(self):
        original = self.seed.read_bytes()
        for _ in range(2):
            result = self.start()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.runtime.read_bytes(), original)
            self.assertEqual(self.seed.read_bytes(), original)

    def test_removal_and_other_changes_survive_restart(self):
        self.assertEqual(self.start().returncode, 0)
        original_seed = self.seed.read_bytes()
        with sqlite3.connect(self.runtime) as conn:
            conn.execute('DELETE FROM recipe_box_item WHERE id=(SELECT min(id) FROM recipe_box_item)')
            conn.execute("INSERT INTO shopping_list (user_id,name,items_json) VALUES (1,'Keep through restart','[]')")
        changed = self.runtime.read_bytes()
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runtime.read_bytes(), changed)
        self.assertEqual(self.seed.read_bytes(), original_seed)

    def test_missing_seed_fails_instead_of_inventing_a_new_catalogue(self):
        self.seed.unlink()
        result = self.start()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('seed database is missing', result.stderr)
        self.assertFalse(self.runtime.exists())


if __name__ == '__main__':
    unittest.main()
