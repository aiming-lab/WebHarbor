"""HTTP regression tests for the OSU mirror."""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

from _support import SEED, SITE, ensure_seed

RUNTIME = SITE / "instance" / "osu.db"


def csrf(response):
    match = re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="csrf_token"',
        response.data,
    )
    assert match, response.request.path
    return (match.group(1) or match.group(2)).decode()


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_seed()
        shutil.rmtree(SITE / "instance", ignore_errors=True)
        (SITE / "instance").mkdir()
        shutil.copy2(SEED, RUNTIME)
        os.environ["OSU_SECRET_KEY"] = "test-only"
        sys.path.insert(0, str(SITE))
        cls.module = importlib.import_module("app")
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.module.db.session.remove()
        shutil.rmtree(SITE / "instance", ignore_errors=True)

    def setUp(self):
        self.client = self.app.test_client()

    def snap(self):
        connection = sqlite3.connect(RUNTIME)
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
                )
            ]
            return {
                table: connection.execute(f'select * from "{table}" order by rowid').fetchall()
                for table in tables
            }
        finally:
            connection.close()

    def login(self, next_url=None):
        route = "/login" + (f"?next={next_url}" if next_url else "")
        page = self.client.get(route)
        return self.client.post(
            route,
            data={"csrf_token": csrf(page), "email": "alice@osu.edu", "password": "test1234"},
            follow_redirects=False,
        )

    def test_all_routes_render(self):
        paths = [
            "/",
            "/about",
            "/academics",
            "/programs",
            "/programs?college=engineering",
            "/research",
            "/departments",
            "/faculty",
            "/news",
            "/events",
            "/athletics",
            "/admissions",
            "/search?q=cancer+research",
            "/login",
            "/register",
            "/_health",
        ]
        with self.app.app_context():
            paths += [f"/programs/{item.slug}" for item in self.module.Program.query.all()]
            paths += [f"/research/{item.slug}" for item in self.module.ResearchCenter.query.all()]
            paths += [f"/departments/{item.slug}" for item in self.module.Department.query.all()]
            paths += [f"/faculty/{item.slug}" for item in self.module.Faculty.query.all()]
            paths += [f"/news/{item.slug}" for item in self.module.NewsArticle.query.all()]
            paths += [f"/events/{item.id}" for item in self.module.Event.query.all()]
            paths += [f"/athletics/{item.slug}" for item in self.module.AthleticTeam.query.all()]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_real_image_assets_are_served(self):
        for item in json.loads((SITE / "image_sources.json").read_text(encoding="utf-8"))["images"]:
            with self.subTest(file=item["file"]):
                response = self.client.get("/static/images/" + item["file"])
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "image/webp")
                self.assertGreater(len(response.get_data()), 5000)
                response.close()

    def test_get_routes_are_read_only(self):
        before = self.snap()
        for path in (
            "/",
            "/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy",
            "/about",
            "/search?q=cancer+research",
            "/events",
        ):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(before, self.snap())

    def test_logout_and_csrf(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)
        for path in ("/logout", "/bookmark/add", "/bookmark/remove"):
            with self.subTest(p=path):
                self.assertEqual(self.client.post(path).status_code, 400)

    def test_open_redirect_rejected_and_login_works(self):
        response = self.login("//evil.invalid")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_invalid_bookmarks_rejected(self):
        self.login()
        page = self.client.get("/programs/juris-doctor-jd")
        token = csrf(page)
        self.assertEqual(
            self.client.post(
                "/bookmark/add",
                data={"csrf_token": token, "item_type": "invalid", "item_id": "1"},
            ).status_code,
            400,
        )
        page = self.client.get("/programs/juris-doctor-jd")
        self.assertEqual(
            self.client.post(
                "/bookmark/add",
                data={"csrf_token": csrf(page), "item_type": "program", "item_id": "99999"},
            ).status_code,
            404,
        )

    def test_valid_bookmark_and_duplicate_are_single_row(self):
        self.login()
        with self.app.app_context():
            program = self.module.Program.query.filter_by(slug="juris-doctor-jd").one()
            program_id = program.id
        page = self.client.get("/programs/juris-doctor-jd")
        data = {
            "csrf_token": csrf(page),
            "item_type": "program",
            "item_id": str(program_id),
            "next": "/programs/juris-doctor-jd",
        }
        self.assertEqual(self.client.post("/bookmark/add", data=data).status_code, 302)
        page = self.client.get("/programs/juris-doctor-jd")
        data["csrf_token"] = csrf(page)
        self.assertEqual(self.client.post("/bookmark/add", data=data).status_code, 302)
        connection = sqlite3.connect(RUNTIME)
        self.assertEqual(
            connection.execute(
                "select count(*) from bookmarks where user_id=1 and item_type=? and item_id=?",
                ("program", program_id),
            ).fetchone()[0],
            1,
        )
        connection.close()

    def test_upcoming_events_visible_with_fixed_clock(self):
        body = self.client.get("/events").get_data(as_text=True)
        self.assertIn("Buckeyes vs. Michigan State Football", body)
        self.assertIn("CFAES Annual Farm Science Review", body)

    def test_request_size_limit(self):
        self.assertEqual(
            self.client.post(
                "/register",
                data=b"x" * (65 * 1024),
                content_type="application/x-www-form-urlencoded",
            ).status_code,
            413,
        )

    def test_task_answers_are_not_on_listings(self):
        athletics = self.client.get("/athletics").get_data(as_text=True)
        self.assertNotIn("Ryan Day", athletics)
        self.assertNotIn("Tom Ryan", athletics)
        self.assertNotIn("11-2", athletics)
        self.assertNotIn("Ohio Stadium", athletics)
        self.assertNotIn("Covelli Center", athletics)
        self.assertNotIn("Value City Arena", athletics)
        self.assertNotIn("National Title", athletics)

        research = self.client.get("/research").get_data(as_text=True)
        self.assertNotIn("Beth Plale", research)
        self.assertNotIn("David Bickel", research)
        self.assertNotIn("William Farrar", research)
        self.assertNotIn("Yann Guezennec", research)

        departments = self.client.get("/departments").get_data(as_text=True)
        self.assertNotIn("James Cogdell", departments)
        self.assertNotIn("100 Mathematics Building", departments)

        programs = self.client.get("/programs?q=Juris+Doctor").get_data(as_text=True)
        self.assertNotIn("90 credits", programs)
        self.assertNotIn("April 1", programs)

        mba = self.client.get("/programs?degree=MBA").get_data(as_text=True)
        self.assertNotIn("April 1", mba)
        self.assertNotIn("GRE Required", mba)
        self.assertNotIn("Not Required", mba)

        search = self.client.get("/search?q=research+expenditures").get_data(as_text=True)
        self.assertNotIn("September 23, 2024", search)
        self.assertNotIn("Jody Sheridan", search)


if __name__ == "__main__":
    unittest.main()
