"""Hermetic fetch routing/hash tests: a fake HF CLI, no network or user assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]


class ScopedAssets(unittest.TestCase):
    def invoke(self, pin, override=None):
        with tempfile.TemporaryDirectory(prefix='wh-fetch-test-') as td:
            root = Path(td)
            (root / 'sites/amtrak').mkdir(parents=True)
            (root / 'scripts').mkdir()
            for name in ('fetch_assets.sh', 'validate_asset_archive.py', 'extract_asset_archive.py', 'sync_assets_to_inventory.py'):
                shutil.copy2(SCRIPTS / name, root / 'scripts' / name)
            archive = root / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                payload = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
                item = tarfile.TarInfo('amtrak/static/images/test.svg')
                item.size = len(payload)
                bundle.addfile(item, io.BytesIO(payload))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            (root / '.assets-revision').write_text('repo: central/assets\nrevision: global-pin\n' + pin.replace('DIGEST', digest))
            (root / 'bin').mkdir()
            hf = root / 'bin/hf'
            hf.write_text('''#!/usr/bin/env python3
import sys,os,json,shutil
from pathlib import Path
args=sys.argv[1:]
Path(os.environ['FETCH_CALL_LOG']).write_text(json.dumps(args))
dest=Path(args[args.index('--local-dir')+1]);dest.mkdir(parents=True,exist_ok=True)
shutil.copyfile(os.environ['FETCH_TEST_ARCHIVE'],dest/args[args.index('--include')+1])
''')
            hf.chmod(0o755)
            env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'],
                   'FETCH_TEST_ARCHIVE': str(archive), 'FETCH_CALL_LOG': str(root / 'call.json')}
            env.pop('ASSETS_REVISION', None)
            if override:
                env['ASSETS_REVISION'] = override
            proc = subprocess.run(['bash', 'scripts/fetch_assets.sh', 'amtrak'], cwd=root, env=env, capture_output=True, text=True)
            args = json.loads((root / 'call.json').read_text()) if (root / 'call.json').exists() else None
            return proc, args, (root / 'sites/amtrak/static/images/test.svg').is_file()

    def test_scoped_immutable_source(self):
        proc, args, extracted = self.invoke('site.amtrak.repo: contributor/assets\nsite.amtrak: ' + 'a'*40 + '\nsite.amtrak.sha256: DIGEST\n')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(args[1], 'contributor/assets')
        self.assertEqual(args[args.index('--revision')+1], 'a'*40)
        self.assertTrue(extracted)

    def test_global_override_bypasses_all_scoped_settings(self):
        proc, args, extracted = self.invoke('site.amtrak.repo: contributor/assets\nsite.amtrak: ' + 'a'*40 + '\nsite.amtrak.sha256: wrong\n', 'override')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(args[1], 'central/assets')
        self.assertEqual(args[args.index('--revision')+1], 'override')
        self.assertTrue(extracted)

    def test_bad_pin_and_hash_fail_before_install(self):
        for pin in ('site.amtrak.repo: contributor/assets\n', 'site.amtrak: main\n', 'site.amtrak.sha256: ' + '0'*64 + '\n'):
            with self.subTest(pin=pin):
                proc, args, extracted = self.invoke(pin)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(extracted)


if __name__ == '__main__':
    unittest.main()
