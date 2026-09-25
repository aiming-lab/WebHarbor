"""Repository contracts after scoped asset pins were retired."""
from __future__ import annotations

import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GlobalAssetPolicy(unittest.TestCase):
    def revision_values(self):
        return {
            key.strip(): value.strip()
            for line in (ROOT / ".assets-revision").read_text().splitlines()
            if ":" in line and not line.lstrip().startswith("#")
            for key, value in [line.split(":", 1)]
        }

    def registered_sites(self):
        text = (ROOT / "websyn_start.sh").read_text()
        return re.search(r"SITES=\((.*?)\)", text, re.S).group(1).split()

    def test_revision_file_uses_one_immutable_global_pin(self):
        values = self.revision_values()
        self.assertEqual(set(values), {"repo", "revision"})
        self.assertRegex(values["revision"], r"^[0-9a-f]{40}$")
        self.assertFalse(any(key.startswith("site.") for key in values))

    def test_manifest_matches_global_pin_and_registered_archive_set(self):
        values = self.revision_values()
        manifest = json.loads((ROOT / "assets-manifest.json").read_text())
        self.assertEqual(manifest["repo"], values["repo"])
        self.assertEqual(manifest["revision"], values["revision"])
        self.assertEqual(set(manifest["archives"]), {f"{site}.tar.gz" for site in self.registered_sites()})
        self.assertEqual(len(manifest["archives"]), len(self.registered_sites()))

    def test_fetch_enforces_pin_and_manifest_for_full_and_single_site_modes(self):
        source = (ROOT / "scripts" / "fetch_assets.sh").read_text()
        self.assertIn('ASSETS_REVISION must equal pinned revision', source)
        self.assertIn('asset_state.py verify-archive', source)
        self.assertIn('asset_state.py verify sites', source)
        self.assertIn('scope: $(( ${#INCLUDES[@]} / 2 )) registered site(s)', source)
        self.assertNotIn('site.$ONLY_SITE', source)
        self.assertNotIn('scoped pin', source.lower())


if __name__ == "__main__":
    unittest.main()
