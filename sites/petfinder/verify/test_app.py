"""HTTP-level regression tests for the reviewed Petfinder mirror."""
from __future__ import annotations

import importlib
import html
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]


def csrf_token(response) -> str:
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    if not match:
        raise AssertionError(f"CSRF token missing from {response.request.path}")
    return match.group(1).decode()


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(prefix="petfinder-app-test-")
        cls.database = Path(cls.tempdir.name) / "petfinder.db"
        os.environ["PETFINDER_DATABASE_URI"] = f"sqlite:///{cls.database}"
        sys.path.insert(0, str(SITE_DIR))
        cls.module = importlib.import_module("app")
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True)
        cls.pristine_database = Path(cls.tempdir.name) / "pristine.db"
        with cls.app.app_context():
            cls.module.db.session.remove()
            cls.module.db.engine.dispose()
        shutil.copyfile(cls.database, cls.pristine_database)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.module.db.session.remove()
        sys.path.remove(str(SITE_DIR))
        os.environ.pop("PETFINDER_DATABASE_URI", None)
        cls.tempdir.cleanup()

    def setUp(self):
        with self.app.app_context():
            self.module.db.session.remove()
            self.module.db.engine.dispose()
        shutil.copyfile(self.pristine_database, self.database)
        self.client = self.app.test_client()

    def login(self, next_url: str | None = None):
        route = "/login" + (f"?next={next_url}" if next_url else "")
        page = self.client.get(route)
        return self.client.post(
            route,
            data={
                "csrf_token": csrf_token(page),
                "email": "alice.j@test.com",
                "password": "TestPass123!",
            },
            follow_redirects=False,
        )

    def snapshot(self):
        connection = sqlite3.connect(self.database)
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            return {
                table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
                for table in tables
            }
        finally:
            connection.close()

    def test_public_pages_and_all_details_render(self):
        paths = [
            "/",
            "/pets",
            "/pets?species=Dog&location=New+York%2C+NY&age=Adult&size=Large&good_with_children=1",
            "/search?q=Nori",
            "/guides",
            "/login",
            "/_health",
        ]
        with self.app.app_context():
            paths += [f"/pets/{row.slug}" for row in self.module.Listing.query.all()]
            paths += [f"/guides/{row.slug}" for row in self.module.Guide.query.all()]
        for route in paths:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route, follow_redirects=True).status_code, 200)

    def test_seed_has_domain_correct_taxonomy_and_facts(self):
        with self.app.app_context():
            self.assertEqual(self.module.Listing.query.count(), 13)
            self.assertEqual(self.module.Guide.query.count(), 5)
            self.assertEqual(self.module.User.query.count(), 4)
            ivy = self.module.Listing.query.filter_by(slug="ivy-calico").one()
            scout = self.module.Listing.query.filter_by(slug="scout-border-collie").one()
            self.assertEqual(ivy.species, "Cat")
            self.assertEqual(scout.species, "Dog")
            self.assertFalse(hasattr(ivy, "score"))
            self.assertFalse(hasattr(ivy, "price"))

    def test_combined_filters_have_one_intended_match(self):
        response = self.client.get(
            "/pets?species=Dog&location=New+York%2C+NY&age=Adult&size=Large&good_with_children=1"
        )
        body = response.get_data(as_text=True)
        self.assertIn("Milo Labrador Mix", body)
        self.assertNotIn("Atlas German Shepherd", body)
        self.assertEqual(body.count('class="pet-card"'), 1)

    def test_filter_controls_have_stable_accessible_names(self):
        body = self.client.get("/pets").get_data(as_text=True)
        for label in ("ANIMAL", "LOCATION", "AGE", "SIZE", "GENDER"):
            self.assertIn(f'aria-label="{label}"', body)

    def test_search_finds_name_and_not_filter_labels(self):
        body = self.client.get("/search?q=Nori").get_data(as_text=True)
        self.assertIn("Nori Rabbit", body)
        empty = self.client.get("/search?q=Distance").get_data(as_text=True)
        self.assertIn("No pets found", empty)

    def test_home_search_is_discoverable_and_location_aware(self):
        home = self.client.get("/").get_data(as_text=True)
        self.assertRegex(home, r'<form[^>]+action="/search"')
        self.assertRegex(home, r'<input[^>]+name="q"')
        matching = self.client.get("/search?q=Nori&location=Seattle%2C+WA").get_data(as_text=True)
        self.assertIn("Nori Rabbit", matching)
        wrong_location = self.client.get("/search?q=Nori&location=Chicago%2C+IL").get_data(as_text=True)
        self.assertIn("No pets found", wrong_location)

    def test_homepage_covers_source_section_sequence(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("Build your bond in the myPurina App", body)
        self.assertEqual(body.count("Pets Available for Adoption Nearby"), 2)
        self.assertIn("30 YEARS OF IMPACT AND JOY", body)
        self.assertIn("30 years of happy tails", body)
        self.assertIn("Dog Adoption Articles", body)
        self.assertIn("Cat Adoption Articles", body)
        for heading in (
            "RESOURCES",
            "ADOPT OR GET INVOLVED",
            "ABOUT DOGS &amp; PUPPIES",
            "ABOUT CATS &amp; KITTENS",
        ):
            self.assertIn(heading, body)

    def test_navigation_menus_are_controls_with_live_local_destinations(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertEqual(body.count('class="nav-menu'), 2)
        self.assertIn("<summary>Find a Pet", body)
        self.assertIn("<summary>All About Pets", body)
        self.assertIn("Find Other Pets", body)
        self.assertIn("OTHER TYPES OF PETS", body)
        self.assertIn('src="/static/js/main.js"', body)

        local_links = {
            html.unescape(target)
            for target in re.findall(r'href="([^"]+)"', body)
            if target.startswith("/") and not target.startswith("/static/")
        }
        self.assertGreaterEqual(len(local_links), 20)
        for target in local_links:
            with self.subTest(target=target):
                response = self.client.get(target, follow_redirects=True)
                self.assertEqual(response.status_code, 200)

    def test_login_is_not_prefilled_and_redirects_post_actions_safely(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertNotIn("alice.j@test.com", body)
        self.assertNotIn("TestPass123!", body)
        response = self.login(next_url="/pets/luna-domestic-shorthair/save")
        self.assertEqual(response.headers["Location"], "/pets/luna-domestic-shorthair")
        external = self.login(next_url="//evil.invalid")
        self.assertEqual(external.headers["Location"], "/account")

    def test_logout_and_mutations_require_post_and_csrf(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.login()
        for route in (
            "/logout",
            "/pets/luna-domestic-shorthair/save",
            "/account/preferences",
            "/pets/nori-rabbit/inquire",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route).status_code, 400)

    def test_pet_card_favorite_controls_are_not_inert(self):
        signed_out = self.client.get("/").get_data(as_text=True)
        self.assertIn('aria-label="Sign in to favorite Luna Domestic Shorthair"', signed_out)
        self.assertIn('href="/login?next=/pets/luna-domestic-shorthair"', signed_out)
        self.login()
        signed_in = self.client.get("/").get_data(as_text=True)
        self.assertIn('action="/pets/luna-domestic-shorthair/save"', signed_in)
        self.assertIn('aria-label="Favorite Luna Domestic Shorthair"', signed_in)

    def test_account_sort_has_a_stable_accessible_name(self):
        self.login()
        body = self.client.get("/account").get_data(as_text=True)
        self.assertIn('aria-label="Default sort"', body)

    def test_save_preferences_and_inquiry_persist(self):
        self.login()
        detail = self.client.get("/pets/luna-domestic-shorthair")
        saved = self.client.post(
            "/pets/luna-domestic-shorthair/save",
            data={"csrf_token": csrf_token(detail)},
            follow_redirects=True,
        )
        self.assertIn("Saved Luna Domestic Shorthair", saved.get_data(as_text=True))

        account = self.client.get("/account")
        updated = self.client.post(
            "/account/preferences",
            data={
                "csrf_token": csrf_token(account),
                "home_location": "Chicago, IL",
                "sort_preference": "Newest pets first",
            },
            follow_redirects=True,
        )
        self.assertIn("Newest pets first", updated.get_data(as_text=True))

        detail = self.client.get("/pets/nori-rabbit")
        inquiry = self.client.post(
            "/pets/nori-rabbit/inquire",
            data={
                "csrf_token": csrf_token(detail),
                "message": "I have a quiet home and would like to meet Nori.",
            },
            follow_redirects=True,
        )
        self.assertIn("Inquiry submitted for Nori Rabbit", inquiry.get_data(as_text=True))

    def test_duplicate_save_is_idempotent_and_accounts_are_isolated(self):
        self.login()
        detail = self.client.get("/pets/luna-domestic-shorthair")
        token = csrf_token(detail)
        for _ in range(2):
            self.client.post(
                "/pets/luna-domestic-shorthair/save",
                data={"csrf_token": token},
                follow_redirects=True,
            )
        with self.app.app_context():
            alice = self.module.User.query.filter_by(email="alice.j@test.com").one()
            luna = self.module.Listing.query.filter_by(slug="luna-domestic-shorthair").one()
            self.assertEqual(
                self.module.SavedItem.query.filter_by(user_id=alice.id, listing_id=luna.id).count(),
                1,
            )

        logout_page = self.client.get("/account")
        logout_token = csrf_token(logout_page)
        self.client.post("/logout", data={"csrf_token": logout_token})
        login_page = self.client.get("/login")
        self.client.post(
            "/login",
            data={
                "csrf_token": csrf_token(login_page),
                "email": "bob.c@test.com",
                "password": "TestPass123!",
            },
        )
        bob_account = self.client.get("/account").get_data(as_text=True)
        self.assertIn("Favorite pets (0)", bob_account)
        self.assertNotIn("Luna Domestic Shorthair", bob_account)

    def test_short_inquiry_is_rejected_without_database_change(self):
        self.login()
        detail = self.client.get("/pets/nori-rabbit")
        response = self.client.post(
            "/pets/nori-rabbit/inquire",
            data={"csrf_token": csrf_token(detail), "message": "Too short"},
            follow_redirects=True,
        )
        self.assertIn("Add a short message for the shelter", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(self.module.Inquiry.query.count(), 0)

    def test_get_routes_leave_database_unchanged(self):
        before = self.snapshot()
        for route in ("/", "/pets", "/search?q=Nori", "/guides", "/login"):
            self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(before, self.snapshot())

    def test_oversized_login_is_rejected(self):
        response = self.client.post(
            "/login",
            data=b"x" * (65 * 1024),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
