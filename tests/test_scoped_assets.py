"""Exercise registered-site/immutable-pin isolation through the real shell script."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


class ScopedAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'scripts').mkdir()
        shutil.copyfile(Path(__file__).parents[1]/'scripts/fetch_assets.sh', self.root/'scripts/fetch_assets.sh')
        for site in ['alpha', 'beta']:
            (self.root/'sites'/site).mkdir(parents=True)
        self.base = 'a'*40; self.scoped = 'b'*40
        (self.root/'.assets-revision').write_text(f'repo: test/assets\nrevision: {self.base}\nsite.beta: {self.scoped}\n')
        (self.root/'bin').mkdir()
        # Fixtures occupy immutable cache locations; mock only the network CLI.
        cli=self.root/'bin/hf'
        cli.write_text('#!/bin/sh\nexit 0\n');cli.chmod(0o755)
        self.env={**os.environ,'PATH':str(self.root/'bin')+':'+os.environ['PATH']}
        self.env.pop('ASSETS_REVISION', None)

    def archive(self,site,pin,member=None):
        dest=self.root/'sites/.cache/tarballs'/pin/f'{site}.tar.gz';dest.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(dest,'w:gz') as tar:
            data=(site+' '+pin).encode();info=tarfile.TarInfo(member or f'{site}/instance_seed/fixture.txt');info.size=len(data)
            tar.addfile(info,io.BytesIO(data))

    def run_fetch(self,*args):
        return subprocess.run(['bash','scripts/fetch_assets.sh',*args],cwd=self.root,env=self.env,text=True,capture_output=True)

    def test_full_fetch_uses_each_pin_and_ignores_unregistered_cache(self):
        self.archive('alpha',self.base);self.archive('beta',self.scoped);self.archive('unexpected',self.base)
        result=self.run_fetch();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.root/'sites/beta/instance_seed/fixture.txt').read_text(),'beta '+self.scoped)
        self.assertFalse((self.root/'sites/unexpected').exists())

    def test_scoped_fetch_does_not_extract_other_sites(self):
        self.archive('alpha',self.base);self.archive('beta',self.scoped)
        result=self.run_fetch('beta');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse((self.root/'sites/alpha/instance_seed').exists())

    def test_missing_pin_archive_fails_without_using_other_revision(self):
        self.archive('beta',self.base)
        self.assertNotEqual(self.run_fetch('beta').returncode,0)
        self.assertFalse((self.root/'sites/beta/instance_seed').exists())

    def test_archive_cannot_write_into_another_site(self):
        self.archive('beta',self.scoped,'alpha/instance_seed/fixture.txt')
        self.assertNotEqual(self.run_fetch('beta').returncode,0)
        self.assertFalse((self.root/'sites/alpha/instance_seed').exists())


if __name__=='__main__':unittest.main()
