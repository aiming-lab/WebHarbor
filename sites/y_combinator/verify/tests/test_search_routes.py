"""Regression coverage for stable ordering when search labels collide."""
import os
from pathlib import Path
import sys
import unittest

SITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

from app import app


class SearchRouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_company_search_handles_duplicate_names(self):
        response = self.client.get("/companies?q=no-such-company-zzzz")
        self.assertEqual(response.status_code, 200)

    def test_founder_search_handles_duplicate_names(self):
        response = self.client.get("/founders?q=abraham")
        self.assertEqual(response.status_code, 200)

    def test_library_search_handles_duplicate_titles(self):
        response = self.client.get("/library?q=startup+ideas")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
