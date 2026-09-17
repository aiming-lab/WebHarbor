"""Exercise revision resolution and real archive installation with an offline HF CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]

class AssetPins(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/'scripts').mkdir(); (self.root/'bin').mkdir()
        for name in ('fetch_assets.sh','validate_asset_archive.py','extract_asset_archive.py','sync_assets_to_inventory.py'):
            shutil.copy2(SCRIPTS/name,self.root/'scripts'/name)
        for site in ('first','second'): (self.root/'sites'/site).mkdir(parents=True)
        (self.root/'.assets-revision').write_text('repo: test/assets\nrevision: '+'a'*40+'\nsite.second: '+'b'*40+'\n')
        hf=self.root/'bin/hf'
        hf.write_text('''#!/usr/bin/env python3
import io,json,os,sys,tarfile
from pathlib import Path
args=sys.argv[1:]; revision=args[args.index('--revision')+1]; out=Path(args[args.index('--local-dir')+1]); out.mkdir(parents=True,exist_ok=True)
with Path('calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
for arg in args:
 if arg.endswith('.tar.gz'):
  site=arg[:-7]; data=revision.encode()
  if site in os.environ.get('MOCK_MISSING_ARCHIVES','').split(','): continue
  with tarfile.open(out/arg,'w:gz') as tar:
   info=tarfile.TarInfo(site+'/static/images/revision.txt'); info.size=len(data); tar.addfile(info,io.BytesIO(data))
'''); hf.chmod(0o755)
        self.env={k:v for k,v in os.environ.items() if k!='ASSETS_REVISION'}
        self.env['PATH']=str(self.root/'bin')+os.pathsep+self.env['PATH']

    def fetch(self,*args,**env):
        return subprocess.run(['bash','scripts/fetch_assets.sh',*args],cwd=self.root,env={**self.env,**env},text=True,capture_output=True)

    def revision(self,site): return (self.root/'sites'/site/'static/images/revision.txt').read_text()

    def test_all_sites_keep_independent_pins(self):
        result=self.fetch(); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.revision('first'),'a'*40); self.assertEqual(self.revision('second'),'b'*40)

    def test_single_site_uses_scoped_pin(self):
        result=self.fetch('second'); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.revision('second'),'b'*40)
        self.assertFalse((self.root/'sites/first/static').exists())

    def test_environment_override_replaces_both_pins(self):
        result=self.fetch(ASSETS_REVISION='c'*40); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.revision('first'),'c'*40); self.assertEqual(self.revision('second'),'c'*40)

    def test_invalid_scoped_pin_fails_before_download(self):
        path=self.root/'.assets-revision'; path.write_text(path.read_text().replace('b'*40,'main'))
        self.assertNotEqual(self.fetch().returncode,0); self.assertFalse((self.root/'calls.jsonl').exists())

    def test_unknown_site_fails_before_download(self):
        self.assertNotEqual(self.fetch('missing').returncode,0); self.assertFalse((self.root/'calls.jsonl').exists())

    def test_build_generated_site_without_required_assets_can_skip_archive(self):
        (self.root/'sites/second/.build-generated-seed').touch()
        for scope in ((), ('second',)):
            with self.subTest(scope=scope):
                result=self.fetch(*scope,MOCK_MISSING_ARCHIVES='second')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('skipping',result.stdout)

    def test_build_generated_site_still_requires_declared_assets(self):
        (self.root/'sites/second/.build-generated-seed').touch()
        for marker in ('.requires-images', '.requires-external-cache'):
            required=self.root/'sites/second'/marker; required.touch()
            for scope in ((), ('second',)):
                with self.subTest(marker=marker,scope=scope):
                    result=self.fetch(*scope,MOCK_MISSING_ARCHIVES='second')
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('expected archive',result.stderr)
            required.unlink()

    def test_non_generated_site_requires_archive(self):
        for scope in ((), ('second',)):
            with self.subTest(scope=scope):
                result=self.fetch(*scope,MOCK_MISSING_ARCHIVES='second')
                self.assertNotEqual(result.returncode,0)
                self.assertIn('expected archive',result.stderr)

if __name__=='__main__': unittest.main()
