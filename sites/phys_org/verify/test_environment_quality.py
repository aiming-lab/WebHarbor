"""Regression checks for Phys.org data quality, task facts, and local assets."""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime
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


@contextmanager
def _connection():
    connection = sqlite3.connect(f"file:{SEED_DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _search_rank(connection: sqlite3.Connection, query: str, target_slug: str,
                 category: str | None = None) -> tuple[int | None, int]:
    stop_words = {
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
        "is", "it", "by", "with", "as", "be", "this", "that", "are", "was",
        "were", "from", "how", "what", "why", "we", "i",
    }
    tokens = [token.casefold() for token in re.split(r"\W+", query) if token and token.casefold() not in stop_words and len(token) > 1]
    sql = "SELECT a.*,c.slug AS category_slug FROM articles a JOIN categories c ON c.id=a.category_id"
    params: tuple[str, ...] = ()
    if category:
        sql += " WHERE c.slug=?"
        params = (category,)
    scored = []
    for row in connection.execute(sql, params):
        blob = f"{row['title']}\n{row['subtitle']}\n{row['body']}".casefold()
        score = sum(token in blob for token in tokens)
        if score:
            scored.append((row, score))
    scored.sort(key=lambda pair: (-pair[1], -datetime.fromisoformat(pair[0]["published_at"]).timestamp()))
    rank = next((index for index, (row, _) in enumerate(scored, 1) if row["slug"] == target_slug), None)
    return rank, len(scored)


class EnvironmentQualityTests(unittest.TestCase):
    def test_agent_pre_pr_sweep_covers_every_registered_site(self) -> None:
        agent_guide = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        startup = (REPO_ROOT / "websyn_start.sh").read_text(encoding="utf-8")
        site_match = re.search(r"SITES=\((.*?)\)", startup, re.DOTALL)
        sweep_match = re.search(r"for p in \$\(seq (\d+) (\d+)\); do", agent_guide)
        self.assertIsNotNone(site_match)
        self.assertIsNotNone(sweep_match)
        sites = site_match.group(1).split()
        sweep_start, sweep_end = map(int, sweep_match.groups())
        self.assertEqual(18, len(sites))
        self.assertEqual((41000, 41000 + len(sites) - 1), (sweep_start, sweep_end))

    def test_task_ids_urls_and_verifier_paths_are_consistent(self) -> None:
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(18, len(rows))
        for index, row in enumerate(rows):
            with self.subTest(task=index):
                self.assertEqual(f"Phys.org--{index}", row["id"])
                self.assertEqual("http://localhost:40017/", row["web"])
                self.assertEqual(f"sites/phys_org/verify/verify_{index}.py", row["verifier_path"])

    def test_only_source_verified_metadata_is_present(self) -> None:
        seed_data = _load_seed_data()
        with _connection() as connection:
            rows = connection.execute(
                "SELECT slug,title,author_name,source_journal,source_institution,doi_url FROM articles"
            ).fetchall()
        self.assertEqual(210, len(rows))
        for row in rows:
            expected = seed_data.SOURCE_METADATA_OVERRIDES.get(row["slug"])
            with self.subTest(slug=row["slug"]):
                if expected:
                    self.assertEqual(expected["title"], row["title"])
                    self.assertRegex(expected["upstream_url"], r"^https://(?:phys\.org|techxplore\.com)/")
                    self.assertTrue(expected["evidence"])
                    self.assertEqual(expected["journal"], row["source_journal"])
                    self.assertEqual(expected["institution"], row["source_institution"])
                    self.assertEqual(expected["doi"], row["doi_url"])
                    self.assertEqual(expected["author"], row["author_name"])
                else:
                    self.assertEqual("", row["source_journal"])
                    self.assertEqual("", row["source_institution"])
                    self.assertEqual("", row["doi_url"])
                    self.assertTrue(row["author_name"])
                    self.assertNotIn(row["author_name"], {
                        "Nina Kowalski", "Elena Yamamoto", "Sarah Patel", "Michael Garcia",
                        "Ananya Nguyen", "Jorge Rossi", "Mei Tanaka", "David Andersen",
                    })

    def test_bodies_and_summaries_do_not_contain_generated_filler(self) -> None:
        filler = (
            "The findings, the team writes",
            "Beyond the immediate result",
            "Independent researchers not involved",
        )
        with _connection() as connection:
            rows = connection.execute("SELECT subtitle,body,doi_url FROM articles").fetchall()
        for row in rows:
            for phrase in filler:
                self.assertNotIn(phrase, row["body"])
            self.assertNotRegex(row["doi_url"], r"/phys\.2026\.\d+$")
            self.assertLessEqual(len(row["subtitle"]), 240)
            if row["subtitle"] != row["body"]:
                self.assertTrue(row["subtitle"].endswith("…"))

    def test_ground_truth_metadata_and_rankings(self) -> None:
        expected = {
            "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-": ("Physical Review Letters", "University of Tübingen"),
            "quantum-circuit-test-finally-exposes-what-has-been-warping-performance": ("Nature Physics", "Massachusetts Institute of Technology"),
            "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio": ("Nature Electronics", "Aalto University"),
            "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement": ("Nature Synthesis", "National University of Singapore"),
            "how-a-single-star-can-reshape-an-entire-galaxy": ("Astronomy & Astrophysics", "Leiden University"),
            "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids": ("Reaction Chemistry & Engineering", ""),
        }
        with _connection() as connection:
            for slug, values in expected.items():
                row = connection.execute(
                    "SELECT source_journal,source_institution FROM articles WHERE slug=?", (slug,)
                ).fetchone()
                self.assertEqual(values, tuple(row))
            hypersonic = connection.execute(
                "SELECT body,source_journal,source_institution FROM articles WHERE slug=?",
                ("cracking-the-code-of-hypersonic-flight-a-decade-of-experiments-maps-tu",),
            ).fetchone()
            self.assertIn("AIAA SCITECH 2026 Forum", hypersonic["body"])
            self.assertEqual(("", ""), (hypersonic["source_journal"], hypersonic["source_institution"]))
            astronomy = connection.execute(
                "SELECT a.slug FROM articles a JOIN categories c ON c.id=a.category_id WHERE c.slug='astronomy' ORDER BY a.views DESC,a.published_at DESC"
            ).fetchall()
            physics = connection.execute(
                "SELECT a.slug FROM articles a JOIN categories c ON c.id=a.category_id WHERE c.slug='physics' ORDER BY a.views DESC,a.published_at DESC"
            ).fetchall()
            trending = connection.execute("SELECT slug FROM articles ORDER BY views DESC,published_at DESC").fetchall()
        self.assertEqual("how-a-single-star-can-reshape-an-entire-galaxy", astronomy[2][0])
        self.assertEqual("jwst-spots-two-early-black-holes-growing-far-faster-than-their-galaxie", astronomy[1][0])
        self.assertEqual("good-vibrations-for-quantum-communications-engineers-couple-single-pho", physics[1][0])
        self.assertEqual("magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-", trending[2][0])
        self.assertEqual("good-vibrations-for-quantum-communications-engineers-couple-single-pho", trending[5][0])

    def test_task_searches_have_distractors_and_nonfirst_targets(self) -> None:
        with _connection() as connection:
            cases = [
                ("quantum", "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio", None, 5),
                ("graphene spin", "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement", None, 2),
                ("graphene spin", "machine-learning-proves-that-graphene-is-hydrophobic", None, 3),
                ("capture materials", "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids", "chemistry", 6),
            ]
            for query, slug, category, expected_rank in cases:
                with self.subTest(query=query, slug=slug):
                    rank, total = _search_rank(connection, query, slug, category)
                    self.assertEqual(expected_rank, rank)
                    self.assertGreaterEqual(total, 6)

    def test_no_empty_categories_are_seeded(self) -> None:
        with _connection() as connection:
            rows = connection.execute(
                "SELECT c.slug,count(a.id) FROM categories c LEFT JOIN articles a ON a.category_id=c.id GROUP BY c.id"
            ).fetchall()
        self.assertEqual(7, len(rows))
        self.assertEqual([], [row for row in rows if row[1] == 0])

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
                names = tar.getnames()
                appledouble = [name for name in names if PurePosixPath(name).name.startswith("._")]
                self.assertIn("phys_org/instance_seed/phys_org.db", names)
            self.assertEqual([], appledouble)


if __name__ == "__main__":
    unittest.main()
