"""Source, asset, seed, task, and integration quality tests for Rotten Tomatoes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[1]


class EnvironmentQualityTests(unittest.TestCase):
    def test_source_catalog_provenance_is_complete(self):
        catalog = json.loads((SITE / 'data/source_catalog.json').read_text())
        self.assertEqual(len(catalog['movies']), 270)
        self.assertEqual(len(catalog['persons']), 3852)
        for movie in catalog['movies']:
            with self.subTest(slug=movie['slug']):
                self.assertEqual(movie['source']['url'], 'https://www.rottentomatoes.com/m/' + movie['slug'])
                self.assertRegex(movie['source']['sha256'], r'^[0-9a-f]{64}$')
                self.assertRegex(movie['cast_source']['sha256'], r'^[0-9a-f]{64}$')
        self.assertFalse(any(person['slug'] == 'undefined' for person in catalog['persons']))

    def test_every_manifested_image_exists_and_matches_hash(self):
        catalog = json.loads((SITE / 'data/source_catalog.json').read_text())
        checks = []
        checks.extend((SITE / 'static/images/posters' / f"{movie['slug']}.jpg", movie.get('poster_sha256'))
                      for movie in catalog['movies'] if movie.get('poster_sha256'))
        checks.extend((SITE / 'static/images/hero' / f"{movie['slug']}.jpg", movie.get('banner_sha256'))
                      for movie in catalog['movies'] if movie.get('banner_sha256'))
        checks.extend((SITE / 'static/images/people' / f"{person['slug']}.jpg", person.get('photo_sha256'))
                      for person in catalog['persons'] if person.get('photo_sha256'))
        self.assertGreaterEqual(len(checks), 3300)
        for path, expected in checks:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_content_snapshots_have_valid_local_assets_and_no_undefined_links(self):
        assets = []
        for name in ('homepage', 'tv_catalog', 'feature_catalog'):
            document = json.loads((SITE / 'data' / f'{name}.json').read_text())
            serialized = json.dumps(document)
            self.assertNotIn('/celebrity/undefined', serialized)
            def walk(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key in {'image', 'banner_image'} and isinstance(item, str) and item.startswith('/static/'):
                            assets.append(item)
                        walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)
            walk(document)
        self.assertGreater(len(assets), 100)
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertTrue((SITE / 'static' / asset.removeprefix('/static/')).is_file())

    def test_cold_seed_is_byte_deterministic(self):
        digests = []
        with tempfile.TemporaryDirectory(prefix='rt-deterministic-') as temporary:
            for index in (1, 2):
                target = Path(temporary) / str(index)
                target.mkdir()
                shutil.copy2(SITE / 'app.py', target / 'app.py')
                shutil.copy2(SITE / 'seed_data.py', target / 'seed_data.py')
                shutil.copytree(SITE / 'data', target / 'data')
                result = subprocess.run([sys.executable, '-c', 'import app'], cwd=target,
                                        env={**os.environ, 'PYTHONHASHSEED': '0'},
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)
                database = target / 'instance/rotten_tomatoes.db'
                digests.append(hashlib.sha256(database.read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1])

    def test_task_manifest_and_registry(self):
        rows = [json.loads(line) for line in (SITE / 'tasks.jsonl').read_text().splitlines() if line.strip()]
        self.assertEqual([row['id'] for row in rows], [f'RottenTomatoes--{value}' for value in (0, 3, 8, 9, 11, 14, 18)])
        for row in rows:
            self.assertEqual(row['web'], 'http://localhost:40021/')
            self.assertTrue((ROOT / row['verifier_path']).is_file())
            self.assertNotIn('answer', row)
        # The registry must still contain this site at its assigned port, and the
        # exposed range must follow the registry length rather than a frozen count.
        startup = (ROOT / 'websyn_start.sh').read_text()
        sites = re.search(r'SITES=\((.*?)\)', startup, re.S).group(1).split()
        self.assertIn('rotten_tomatoes', sites)
        self.assertEqual(40000 + sites.index('rotten_tomatoes'), 40021)
        self.assertIn('fedex', sites)
        self.assertEqual(40000 + sites.index('fedex'), 40024)
        self.assertIn('webmd_doctor', sites)
        self.assertEqual(40000 + sites.index('webmd_doctor'), 40025)
        self.assertIn("'ted', 'osu', 'rotten_tomatoes'", (ROOT / 'control_server.py').read_text())
        self.assertIn(f'40000-{40000 + len(sites) - 1}', (ROOT / 'Dockerfile').read_text())
        self.assertTrue((SITE / '.build-generated-seed').is_file())
        self.assertTrue((SITE / '.requires-images').is_file())
        self.assertTrue((SITE / '.requires-external-cache').is_file())

    def test_templates_do_not_hotlink_images(self):
        for template in (SITE / 'templates').rglob('*.html'):
            with self.subTest(template=template.name):
                self.assertIsNone(re.search(r'<img[^>]+src=["\']https?://', template.read_text(), re.I))


if __name__ == '__main__':
    unittest.main()
