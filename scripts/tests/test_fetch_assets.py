"""Hermetic tests for the global-pin, fail-closed asset fetch pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]


class AssetFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        (self.root / "bin").mkdir()
        for name in (
            "fetch_assets.sh", "validate_asset_archive.py", "extract_asset_archive.py",
            "asset_state.py", "asset_transaction.py", "check_seed_databases.py",
        ):
            shutil.copy2(SCRIPTS / name, self.root / "scripts" / name)
        for site in ("first", "second"):
            directory = self.root / "sites" / site
            directory.mkdir(parents=True)
            (directory / ".build-generated-seed").touch()
        self.revision = "a" * 40
        (self.root / ".assets-revision").write_text(
            f"repo: test/assets\nrevision: {self.revision}\n"
        )
        hf = self.root / "bin" / "hf"
        hf.write_text("""#!/usr/bin/env python3
import io,json,os,sys,tarfile
from pathlib import Path
args=sys.argv[1:]
revision=args[args.index('--revision')+1]
out=Path(args[args.index('--local-dir')+1]);out.mkdir(parents=True,exist_ok=True)
with Path('calls.jsonl').open('a') as stream: stream.write(json.dumps(args)+'\\n')
for arg in args:
 if not arg.endswith('.tar.gz'): continue
 site=arg[:-7]
 if site in os.environ.get('MOCK_MISSING_ARCHIVES','').split(','): continue
 target=out/arg
 if target.exists(): continue
 data=revision.encode()
 with tarfile.open(target,'w:gz') as bundle:
  info=tarfile.TarInfo(site+'/static/images/revision.txt');info.size=len(data);bundle.addfile(info,io.BytesIO(data))
""")
        hf.chmod(0o755)
        self.environment = {key: value for key, value in os.environ.items() if key != "ASSETS_REVISION"}
        self.environment["PATH"] = str(self.root / "bin") + os.pathsep + self.environment["PATH"]

    def fetch(self, *args, **environment):
        return subprocess.run(
            ["bash", "scripts/fetch_assets.sh", *args], cwd=self.root,
            env={**self.environment, **environment}, text=True, capture_output=True,
            timeout=60,
        )

    def refresh(self):
        result = self.fetch("--refresh-manifest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def extracted_revision(self, site):
        return (self.root / "sites" / site / "static" / "images" / "revision.txt").read_text()

    def clear_cache(self):
        shutil.rmtree(self.root / "sites" / ".cache", ignore_errors=True)
        (self.root / "calls.jsonl").unlink(missing_ok=True)

    def test_full_refresh_then_ordinary_fetch_use_one_global_pin(self):
        refreshed = self.refresh()
        self.assertIn("scope: 2 registered site(s)", refreshed.stdout)
        self.assertEqual(self.extracted_revision("first"), self.revision)
        self.assertEqual(self.extracted_revision("second"), self.revision)
        ordinary = self.fetch()
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertIn("asset state matches test/assets@" + self.revision, ordinary.stdout)

    def test_single_site_uses_global_pin_and_tracked_manifest(self):
        self.refresh()
        shutil.rmtree(self.root / "sites" / "second" / "static")
        result = self.fetch("second")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.extracted_revision("second"), self.revision)
        self.assertIn("archive matches tracked manifest: second.tar.gz", result.stdout)

    def test_different_environment_override_is_rejected_before_download(self):
        result = self.fetch(ASSETS_REVISION="b" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must equal pinned revision", result.stderr)
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_equal_environment_override_is_allowed(self):
        result = self.fetch("--refresh-manifest", ASSETS_REVISION=self.revision)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]
        self.assertTrue(all(call[call.index("--revision") + 1] == self.revision for call in calls))

    def test_unknown_site_fails_before_download(self):
        result = self.fetch("missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown site", result.stderr)
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_build_generated_site_archive_is_required_for_full_fetch(self):
        result = self.fetch("--refresh-manifest", MOCK_MISSING_ARCHIVES="second")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("archive set mismatch", result.stderr)
        self.assertIn("second", result.stderr)

    def test_build_generated_site_archive_is_required_for_single_fetch(self):
        self.refresh()
        self.clear_cache()
        result = self.fetch("second", MOCK_MISSING_ARCHIVES="second")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracked archive is missing", result.stderr)

    def test_tampered_single_site_archive_is_rejected(self):
        self.refresh()
        archive = self.root / "sites" / ".cache" / "tarballs" / self.revision / "second.tar.gz"
        archive.write_bytes(b"tampered archive")
        result = self.fetch("second")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match tracked asset manifest", result.stderr)


if __name__ == "__main__":
    unittest.main()
