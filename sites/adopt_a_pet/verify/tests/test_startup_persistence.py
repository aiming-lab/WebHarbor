"""Process restarts preserve legitimate empty state; fresh builds are reproducible."""
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

class StartupPersistence(unittest.TestCase):
    def test_seed_restart_and_removed_last_favorite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            def start(name):
                target=root/name
                target.mkdir(exist_ok=True)
                shutil.copy2(Path(__file__).resolve().parents[2]/'app.py',target/'app.py')
                subprocess.run([sys.executable,'-c','import app'],cwd=target,check=True,capture_output=True)
                return target/'instance/adopt_a_pet.db'
            seed=start('one');original=seed.read_bytes()
            self.assertEqual(original,start('two').read_bytes())
            self.assertEqual(original,start('one').read_bytes())
            with sqlite3.connect(seed) as con:
                self.assertEqual(con.execute('select count(*) from favorite').fetchone()[0],1)
                con.execute('delete from favorite')
            removed=seed.read_bytes()
            self.assertEqual(removed,start('one').read_bytes())
            with sqlite3.connect(seed) as con:
                self.assertEqual(con.execute('select count(*) from favorite').fetchone()[0],0)
            seed.write_bytes(original)
            self.assertEqual(original,start('one').read_bytes())
