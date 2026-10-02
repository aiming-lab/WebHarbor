"""Canonical URLs retain legacy grading semantics, including query constraints."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class SearchEvidenceTests(unittest.TestCase):
    def test_canonical_urls_preserve_query_filters_and_origin(self):
        cases = {
            'amazon': ('/s?k=Mac+mini&color=blue', '/search?q=Mac+mini&color=blue'),
            'booking': ('/searchresults.html?ss=London&breakfast=1', '/search?q=London&breakfast=1'),
            'apple': ('/search/Mac%20mini?sort=price', '/search?q=Mac+mini&sort=price'),
            'google_map': ('/maps/search/A%2FB%20%26%20C?hours=24h', '/search?q=A%2FB+%26+C&hours=24h'),
            'espn': ('/search/_/q/Los%20Angeles?type=teams', '/search?q=Los+Angeles&type=teams'),
            'coursera': ('/search?query=Python&level=beginner', '/search?q=Python&level=beginner'),
            'huggingface': ('/search/full-text?q=bert&type=model', '/search?q=bert&type=model'),
            'cambridge_dictionary': ('/search/english-thesaurus/direct/?q=happy', '/thesaurus?q=happy'),
        }
        for site, (canonical, legacy) in cases.items():
            with self.subTest(site=site):
                spec = importlib.util.spec_from_file_location(site, ROOT / f'sites/{site}/verify/verify_lib.py')
                mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                for origin in ('http://localhost:45000', 'https://elsewhere.test'):
                    self.assertEqual(mod.search_evidence_url(origin + canonical), origin + legacy)
                self.assertEqual(mod.search_evidence_url(legacy), legacy)
                self.assertEqual(mod.search_evidence_url('/product/search?q=other'), '/product/search?q=other')
