"""Regression checks for arXiv adjacent-duplicate LaTeX metadata cleanup.

Run with:

    python3 -m unittest discover -s sites/arxiv/tests -v
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

from metadata_cleaning import (  # noqa: E402
    clean_arxiv_metadata_text,
    clean_paper_metadata_fields,
)

PAPERS_JSON = SITE / "papers.json"
APP_PY = SITE / "app.py"

# Fixtures from aiming-lab/WebHarbor#16 plus nearby scrape artifacts.
ISSUE_CASES = [
    (
        r"A Natural \gtrsim 100\times\gtrsim 100\times Telescope: "
        r"Discovery of the Strongly Lensed Type II SN 2025mkn at z=1.37z=1.37",
        r"A Natural $\gtrsim 100\times$ Telescope: "
        r"Discovery of the Strongly Lensed Type II SN 2025mkn at $z=1.37$",
    ),
    (
        r"Tschirnhausen bundles of sextic covers of \mathbb{P}^1\mathbb{P}^1",
        r"Tschirnhausen bundles of sextic covers of \mathbb{P}^1",
    ),
    (
        r"The \mathcal{N}=1\mathcal{N}=1 Super-Grassmannian for CFT_3_3 "
        r"and a Foray on AdS and Cosmological Correlators",
        r"The \mathcal{N}=1 Super-Grassmannian for CFT_3 "
        r"and a Foray on AdS and Cosmological Correlators",
    ),
    (
        r"Average shifted convolution sum for "
        r"GL(d_1)\times GL(d_2)GL(d_1)\times GL(d_2)",
        r"Average shifted convolution sum for GL(d_1)\times GL(d_2)",
    ),
    (
        r"Critical values of LL-functions of residual representations of "
        r"\mathrm{GL}_4\mathrm{GL}_4",
        r"Critical values of LL-functions of residual representations of "
        r"\mathrm{GL}_4",
    ),
    (
        r"Nuclear forward scattering of Bessel beams in ^{229}^{229}Th:CaF_2_2",
        r"Nuclear forward scattering of Bessel beams in ^{229}Th:CaF_2",
    ),
    (
        r"Chemistry and ro-vibrational excitation of CH^+^+ "
        r"in the Planetary Nebula NGC 7027",
        r"Chemistry and ro-vibrational excitation of CH^+ "
        r"in the Planetary Nebula NGC 7027",
    ),
]

PAPERS_JSON_IDS = {
    "2604.07983": {
        "contains": [r"$\gtrsim 100\times$", r"$z=1.37$", "SN 2025mkn"],
        "forbidden": [r"\gtrsim 100\times\gtrsim 100\times", "z=1.37z=1.37"],
    },
    "2604.04709": {
        "contains": [r"\mathbb{P}^1"],
        "forbidden": [r"\mathbb{P}^1\mathbb{P}^1"],
    },
    "2604.07446": {
        "contains": [r"\mathcal{N}=1", "CFT_3"],
        "forbidden": [r"\mathcal{N}=1\mathcal{N}=1", "CFT_3_3"],
    },
    "2206.03566": {
        "contains": [r"\mathbb{R}^4"],
        "forbidden": [r"\mathbb{R}^4\mathbb{R}^4"],
    },
    "2511.23096": {
        "contains": [r"GL(d_1)\times GL(d_2)"],
        "forbidden": [r"GL(d_1)\times GL(d_2)GL(d_1)\times GL(d_2)"],
    },
    "2407.13464": {
        "contains": [r"\mathrm{GL}_4"],
        "forbidden": [r"\mathrm{GL}_4\mathrm{GL}_4"],
    },
}

UNRELATED_TITLES = [
    "The Cone Conjecture for Enriques Surfaces in any Characteristic",
    "Semantic-Aware UAV Command and Control for Efficient IoT Data Collection",
    "Metacat: a categorical framework for formal systems",
    "Approaching the thermodynamic limit of a bounded one-component plasma",
    "Perfect 11-factorisations of K_{11,11}",
    "Ads in AI Chatbots? An Analysis of How Large Language Models Navigate Conflicts of Interest",
]

_REMAINING_DUP_PATTERNS = [
    re.compile(r"(\\mathbb\{(?:[^{}]|\{[^{}]*\})*\}\^?[A-Za-z0-9+-]*)\1"),
    re.compile(r"(\\mathcal\{[^}]+\}(?:=[0-9A-Za-z]+)?)\1"),
    re.compile(r"(\\mathrm\{[^}]+\}(?:[_^][A-Za-z0-9]+)?)\1"),
    re.compile(r"(\\gtrsim\s+\d+\\times)\1"),
    re.compile(r"\b(z=[0-9.]+)\1"),
    re.compile(r"(GL\([^)]+\)\\times GL\([^)]+\))\1"),
    re.compile(r"(\^\{?\d+\}?)\1"),
    re.compile(r"(\^\+)\1"),
]


class CleanupHelperTests(unittest.TestCase):
    def test_issue_fixtures_collapse_to_expected(self):
        for raw, expected in ISSUE_CASES:
            with self.subTest(raw=raw[:60]):
                self.assertEqual(expected, clean_arxiv_metadata_text(raw))

    def test_cleanup_is_idempotent(self):
        for raw, expected in ISSUE_CASES:
            with self.subTest(raw=raw[:60]):
                once = clean_arxiv_metadata_text(raw)
                self.assertEqual(expected, once)
                self.assertEqual(once, clean_arxiv_metadata_text(once))

    def test_does_not_rewrite_unrelated_titles(self):
        for title in UNRELATED_TITLES:
            with self.subTest(title=title):
                self.assertEqual(title, clean_arxiv_metadata_text(title))

    def test_preserves_intentional_double_prime_and_log_log(self):
        arcseconds = r"0.83$^{\prime\prime}$ from a $z=0.42$ elliptical galaxy"
        self.assertEqual(arcseconds, clean_arxiv_metadata_text(arcseconds))
        log_log = r"(\log p)^{1/14} (\log \log p)^{3/7-\epsilon}"
        self.assertEqual(log_log, clean_arxiv_metadata_text(log_log))
        percent = "We observe an increase of up to 22.80% with the combination"
        self.assertEqual(percent, clean_arxiv_metadata_text(percent))
        speedup = r"achieving up to 11$\times$ speedup over BF16"
        self.assertEqual(speedup, clean_arxiv_metadata_text(speedup))

    def test_empty_and_none_passthrough(self):
        self.assertIsNone(clean_arxiv_metadata_text(None))
        self.assertEqual("", clean_arxiv_metadata_text(""))

    def test_clean_paper_metadata_fields_only_reports_changes(self):
        paper = {
            "title": r"\mathbb{P}^1\mathbb{P}^1",
            "abstract": "No duplicates here.",
            "comments": "12 pages, 5 figures",
            "journal_ref": "",
        }
        self.assertEqual(
            {"title": r"\mathbb{P}^1"},
            clean_paper_metadata_fields(paper),
        )


class PapersJsonRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.papers = json.loads(PAPERS_JSON.read_text())
        cls.by_id = {paper.get("arxiv_id"): paper for paper in cls.papers}

    def test_papers_json_issue_ids(self):
        for arxiv_id, checks in PAPERS_JSON_IDS.items():
            with self.subTest(arxiv_id=arxiv_id):
                paper = self.by_id.get(arxiv_id)
                self.assertIsNotNone(paper, f"missing arXiv fixture {arxiv_id}")
                cleaned = clean_arxiv_metadata_text(paper.get("title", ""))
                for fragment in checks["contains"]:
                    self.assertIn(fragment, cleaned)
                for fragment in checks["forbidden"]:
                    self.assertNotIn(fragment, cleaned)

    def test_papers_json_titles_have_no_remaining_known_duplicates(self):
        failures = []
        for paper in self.papers:
            cleaned = clean_arxiv_metadata_text(paper.get("title", "") or "")
            for pattern in _REMAINING_DUP_PATTERNS:
                if pattern.search(cleaned):
                    failures.append((paper.get("arxiv_id"), cleaned, pattern.pattern))
                    break
        self.assertFalse(
            failures,
            "duplicated LaTeX fragments remain:\n"
            + "\n".join(f"{pid}: {title}" for pid, title, _ in failures[:20]),
        )

    def test_cleanup_is_idempotent_across_seed_corpus(self):
        for paper in self.papers:
            for field in ("title", "abstract", "comments", "journal_ref"):
                raw = paper.get(field) or ""
                once = clean_arxiv_metadata_text(raw)
                twice = clean_arxiv_metadata_text(once)
                if once != twice:
                    self.fail(f"{paper.get('arxiv_id')} {field} not idempotent")


class WiringTests(unittest.TestCase):
    def test_app_wires_cleanup_into_seed_and_startup_backfill(self):
        src = APP_PY.read_text()
        self.assertIn(
            "from metadata_cleaning import clean_arxiv_metadata_text", src
        )
        self.assertIn('clean_arxiv_metadata_text(rp.get("title"', src)
        self.assertIn("def normalize_paper_metadata", src)
        self.assertIn("normalize_paper_metadata()", src)
        # Startup order: normalize packaged rows before synthesizing empty
        # abstracts from titles, so backfilled abstracts do not inherit
        # duplicated fragments.
        norm_at = src.rfind("normalize_paper_metadata()")
        gaps_at = src.rfind("backfill_paper_gaps()")
        self.assertGreater(norm_at, 0)
        self.assertGreater(gaps_at, norm_at)


if __name__ == "__main__":
    unittest.main()
