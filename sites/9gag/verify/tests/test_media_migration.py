"""The tracked correction must preserve fixture facts and reset byte identity."""
import hashlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SITE))
from migrate_seed import migrate


class MediaMigrationTests(unittest.TestCase):
    def test_only_curated_media_changes_and_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '9gag.db'
            shutil.copy2(SITE / 'instance_seed/9gag.db', target)
            with sqlite3.connect(target) as db:
                db.execute("UPDATE post SET image='posts/unrelated.jpg', post_type='Photo' WHERE id BETWEEN 11 AND 80")
                columns = [row[1] for row in db.execute('PRAGMA table_info(post)') if row[1] not in {'image','post_type'}]
                query = f"SELECT {','.join(columns)} FROM post ORDER BY id"
                facts = db.execute(query).fetchall()
                captured = db.execute('SELECT * FROM post WHERE id <= 10 ORDER BY id').fetchall()
                other = {table: db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
                         for table in ('user','comment','vote','saved_post','hidden_post','report')}
            self.assertEqual(migrate(target), 70)
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute(query).fetchall(), facts)
                self.assertEqual(db.execute('SELECT * FROM post WHERE id <= 10 ORDER BY id').fetchall(), captured)
                self.assertEqual(db.execute("SELECT count(*) FROM post WHERE id BETWEEN 11 AND 80 AND image='' AND post_type='Text'").fetchone()[0], 70)
                for table, rows in other.items():
                    self.assertEqual(db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall(), rows)
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(migrate(target), 0)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'missing.db'
            with self.assertRaises(FileNotFoundError):
                migrate(target)
            self.assertFalse(target.exists())
