"""Regression checks for the Phys.org asset and seed review findings."""

from __future__ import annotations

import importlib.util
import re
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path, PurePosixPath


SITE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SITE_DIR.parents[1]
SEED_DB = SITE_DIR / "instance_seed" / "phys_org.db"


def _load_seed_data():
    spec = importlib.util.spec_from_file_location("phys_org_seed_data", SITE_DIR / "seed_data.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EnvironmentQualityTests(unittest.TestCase):
    def test_agent_pre_pr_sweep_covers_every_registered_site(self) -> None:
        agent_guide = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        startup = (REPO_ROOT / "websyn_start.sh").read_text(encoding="utf-8")
        site_match = re.search(r"SITES=\((.*?)\)", startup, re.DOTALL)
        sweep_match = re.search(
            r"for p in \$\(seq (\d+) (\d+)\); do", agent_guide
        )
        self.assertIsNotNone(site_match)
        self.assertIsNotNone(sweep_match)
        sites = site_match.group(1).split()
        sweep_start, sweep_end = map(int, sweep_match.groups())
        self.assertEqual((41000, 41000 + len(sites) - 1), (sweep_start, sweep_end))

    def test_subsection_journal_fix_preserves_legacy_institutions(self) -> None:
        seed_data = _load_seed_data()
        cases = [
            (
                "operational-test-demonstrates-100-electric-furnace-for-ceramic-frit-me",
                "Engineering",
                "Microsoft Research",
            ),
            (
                "no-more-burning-and-exploding-batteries-study-addresses-low-temperatur",
                "Engineering",
                "Microsoft Research",
            ),
            (
                "end-of-life-batteries-yield-next-generation-cathode-under-mild-conditi",
                "Engineering",
                "Tsinghua University",
            ),
            (
                "light-tunable-polarization-sensor-could-sharpen-self-driving-cars-and-",
                "Engineering",
                "KAIST",
            ),
            (
                "60-of-us-teens-have-tried-ai-chatbots-11-4-use-them-almost-daily",
                "Machine learning & AI",
                "University of California, Berkeley",
            ),
        ]

        for slug, subsection, expected_institution in cases:
            with self.subTest(slug=slug):
                journal, institution = seed_data.source_metadata(
                    "technology", subsection, slug
                )
                self.assertIn(
                    journal,
                    seed_data.journal_pool("technology", subsection),
                )
                self.assertEqual(expected_institution, institution)

    def test_no_empty_categories_are_seeded(self) -> None:
        seed_data = _load_seed_data()
        self.assertNotIn("other", [row[0] for row in seed_data.CATEGORIES])
        connection = sqlite3.connect(SEED_DB)
        try:
            rows = connection.execute(
                "SELECT c.slug,count(a.id) FROM categories c "
                "LEFT JOIN articles a ON a.category_id=c.id GROUP BY c.id"
            ).fetchall()
        finally:
            connection.close()
        self.assertTrue(rows)
        self.assertEqual([], [row for row in rows if row[1] == 0])

    def test_engineering_articles_use_subsection_specific_journals(self) -> None:
        seed_data = _load_seed_data()
        pool = seed_data.journal_pool("technology", "Engineering")
        self.assertNotIn("ACM Computing Surveys", pool)
        connection = sqlite3.connect(SEED_DB)
        try:
            rows = connection.execute(
                "SELECT title,source_journal FROM articles WHERE subsection='Engineering'"
            ).fetchall()
        finally:
            connection.close()
        self.assertTrue(rows)
        self.assertEqual([], [row for row in rows if row[1] not in pool])

    def test_asset_packer_excludes_appledouble_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phys-org-assets-") as temp_dir:
            subprocess.run(
                [str(REPO_ROOT / "scripts" / "extract_assets.sh"), temp_dir, "phys_org"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            archive = Path(temp_dir) / "phys_org.tar.gz"
            with tarfile.open(archive, "r:gz") as tar:
                appledouble = [
                    name for name in tar.getnames()
                    if PurePosixPath(name).name.startswith("._")
                ]
            self.assertEqual([], appledouble)


if __name__ == "__main__":
    unittest.main()
