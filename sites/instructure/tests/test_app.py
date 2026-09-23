"""HTTP-level regression tests for the instructure mirror.

Run:  cd sites/instructure && python -m pytest tests/ -q

The suite runs against an isolated throwaway database seeded from the tracked
source snapshots, so it never touches the dev instance.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

SITE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_DIR))

_TMP = tempfile.mkdtemp(prefix="instructure-app-test-")
os.environ["INSTRUCTURE_DB_PATH"] = f"sqlite:///{_TMP}/instructure.db"

from app import app, db  # noqa: E402
import seed_data  # noqa: E402

seed_data.main()
app.config.update(TESTING=True)


class InstructureMirrorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def csrf(self, response, prefix: str = "") -> str:
        m = re.search(
            rf'name="{prefix}csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True))
        assert m, f"csrf token missing on {response.request.path}"
        return m.group(1)

    # ---------- structural pages ----------

    def test_health(self):
        r = self.client.get("/_health")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.get_data(as_text=True))
        self.assertTrue(data["ok"])
        self.assertEqual(data["site"], "instructure")
        self.assertGreaterEqual(data["counts"]["resources"], 700)
        self.assertGreaterEqual(data["counts"]["events"], 39)
        self.assertGreaterEqual(data["counts"]["jobs"], 43)

    def test_homepage_sections(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        for needle in ["InstructureCon", "Canvas", "Mastery", "Parchment",
                       "8,000", "19M", "Accolades", "logo-strip", "newsletter-strip"]:
            self.assertIn(needle, html)

    def test_404(self):
        r = self.client.get("/no/such/page")
        self.assertEqual(r.status_code, 404)

    # ---------- resource hub ----------

    def test_hub_listing_renders_cards(self):
        r = self.client.get("/resources/case-studies")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Case Studies", html)
        self.assertIn("results", html)
        self.assertGreaterEqual(html.count('class="res-item"'), 10)

    def test_hub_product_filter_matches_helena(self):
        r = self.client.get("/resources/case-studies?product=Parchment+Services")
        self.assertEqual(r.status_code, 200)
        self.assertIn("digitized-and-disaster-proof-k-12-records-helena-public-schools",
                      r.get_data(as_text=True))

    def test_hub_org_filter_webinars_business(self):
        r = self.client.get("/resources/webinars?org=Business")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        m = re.search(r'class="results-count">([^<]+)<', html)
        assert m, "results-count missing on webinar hub"
        self.assertIn("13", m.group(1))

    def test_hub_pagination(self):
        r = self.client.get("/resources/ebooks?page=2")
        self.assertEqual(r.status_code, 200)
        self.assertIn("page=3", r.get_data(as_text=True))

    def test_detail_pages_render_bodies(self):
        probes = [
            "/resources/case-studies/edison-high-school-case-study",
            "/resources/blog/minutes-are-wrong-measure",
            "/resources/webinars/design-matters-key-lessons-better-canvas-courses",
            "/resources/ebooks/external-education-playbook",
        ]
        for url in probes:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertGreater(len(r.get_data(as_text=True)), 4000, url)

    def test_case_study_stat_bar(self):
        r = self.client.get(
            "/resources/case-studies/staying-course-better-benchmarks-madison-county")
        html = r.get_data(as_text=True)
        self.assertIn("12,700", html)
        self.assertIn("A rating", html)

    def test_search(self):
        r = self.client.get("/search?srch=Helena")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Helena Public Schools", html)

    def test_press_release_listing_and_detail(self):
        r = self.client.get("/news/public-relations")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertGreaterEqual(html.count("/press-release/"), 10)
        m = re.search(r'href="/press-release/([a-z0-9-]+)"', html)
        assert m
        r = self.client.get(f"/press-release/{m.group(1)}")
        self.assertEqual(r.status_code, 200)

    def test_events_careers_news_support(self):
        for url, needle in [
            ("/events", "Events"),
            ("/about/careers", "Openings"),
            ("/news", "Instructure in the News"),
            ("/support/canvas-support-faq", "FAQ"),
            ("/about/leadership", "Leadership"),
        ]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn(needle, r.get_data(as_text=True), url)

    # ---------- forms ----------

    def test_demo_form_flow(self):
        r = self.client.get("/request-demo")
        token = self.csrf(r)
        data = {
            "csrf_token": token,
            "first_name": "Jordan", "last_name": "Reyes",
            "email": "jordan.reyes@example.com",
            "phone": "555-0100", "job_title": "Director",
            "organization": "Riverbend College", "organization_type": "Higher Ed",
            "country": "United States", "state": "Ohio",
            "needs": "I want to connect with sales",
            "message": "We want to modernize our course delivery next year.",
            "heard": "From a peer", "consent": "y",
        }
        r = self.client.post("/request-demo", data=data, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Thanks! An Instructure team member will reach out",
                      r.get_data(as_text=True))

    def test_contact_validation(self):
        r = self.client.get("/contact-us")
        token = self.csrf(r)
        data = {"csrf_token": token, "first_name": "A", "last_name": "B",
                "email": "not-an-email", "message": "hi"}
        r = self.client.post("/contact-us", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertIn("err", r.get_data(as_text=True))

    def test_newsletter_subscribe(self):
        r = self.client.post("/newsletter/subscribe",
                             data={"email": "news@example.com"},
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("on the list!", r.get_data(as_text=True))

    def test_download_gate(self):
        url = "/resources/case-studies/edison-high-school-case-study/download"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        token = self.csrf(r, prefix="gate-")
        data = {
            "gate-csrf_token": token,
            "gate-first_name": "Priya", "gate-last_name": "Nair",
            "gate-email": "priya.nair@example.com",
            "gate-organization": "Edison High School",
            "gate-organization_type": "K12",
            "gate-country": "United States",
            "gate-needs": "I'm a teacher looking for product information",
            "gate-message": "We would like a copy of this case study for our board.",
            "gate-consent": "y",
        }
        r = self.client.post(url, data=data, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("download", r.get_data(as_text=True).lower())

    # ---------- accounts ----------

    def test_login_and_saved(self):
        r = self.client.get("/login")
        token = self.csrf(r)
        r = self.client.post("/login", data={
            "csrf_token": token, "email": "alice.j@test.com", "password": "TestPass123!",
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/account/saved")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Staying the Course for Better Benchmarks in Madison County",
                      r.get_data(as_text=True))
        self.client.get("/logout")

    def test_webinar_registration_flow(self):
        r = self.client.get("/login")
        token = self.csrf(r)
        self.client.post("/login", data={
            "csrf_token": token, "email": "carol.d@test.com", "password": "TestPass123!",
        }, follow_redirects=True)
        url = "/resources/webinars/design-matters-key-lessons-better-canvas-courses"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"{url}/register", data={"next": url},
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("registered", r.get_data(as_text=True).lower())
        self.client.get("/logout")


if __name__ == "__main__":
    import unittest
    unittest.main()
