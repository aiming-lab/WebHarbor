"""Run in an isolated instance: python -m unittest discover -s tests -v."""

import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

SITE = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory(prefix="craigslist-tests-")
os.environ["CRAIGSLIST_INSTANCE"] = TEMP.name
import app as site


class Routes(unittest.TestCase):
    def setUp(self):
        with site.app.app_context():
            site.db.session.remove()
            site.db.engine.dispose()
        shutil.copyfile(
            SITE / "instance_seed/craigslist.db", Path(TEMP.name) / "craigslist.db"
        )
        self.client = site.app.test_client()

    def token(self, path="/login"):
        html = self.client.get(path).text
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, email="alice.j@test.com"):
        return self.client.post(
            "/login",
            data=dict(csrf_token=self.token(), email=email, password="TestPass123!"),
        )

    def post(self, path, **data):
        with self.client.session_transaction() as session:
            data["csrf_token"] = session["csrf_token"]
        return self.client.post(path, data=data)

    def test_all_read_routes_no_db_mutation(self):
        self.login()
        p = Path(TEMP.name) / "craigslist.db"
        before = p.read_bytes()
        routes = [
            "/",
            "/search",
            "/search/furniture?q=office+chair",
            "/account",
            "/messages",
            "/saved",
            "/hidden",
            "/account/edit",
            "/post",
            "/about/help",
            "/about/safety",
            "/about/privacy",
            "/about/terms",
            "/about/about",
        ]
        with site.app.app_context():
            routes += [f"/d/{x.slug}/{x.id}.html" for x in site.Listing.query.all()]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(before, p.read_bytes())

    def test_sort_with_query_and_combined_filters(self):
        with site.app.test_request_context(
            "/search/furniture?q=office+chair&area=east+bay&max_price=100&has_image=1&sort=price_asc"
        ):
            rows = site.filtered_listings("furniture")
            self.assertGreater(len(rows), 1)
            self.assertEqual([r.price for r in rows], sorted(r.price for r in rows))
            self.assertTrue(
                all(r.area == "east bay" and r.image and r.price <= 100 for r in rows)
            )

    def test_filters_validation_and_title_only(self):
        for url in [
            "/search?min_price=-5",
            "/search?min_price=100&max_price=20",
            "/search?area=invalid",
            "/search/no-such-category",
        ]:
            self.assertIn(self.client.get(url).status_code, [400, 404])
        with site.app.test_request_context("/search?q=Colamy&title_only=1"):
            self.assertEqual(site.filtered_listings(), [])
        with site.app.test_request_context("/search?q=Colamy"):
            self.assertEqual([r.id for r in site.filtered_listings()], [2])

    def test_guest_hide_unhide_and_csrf(self):
        self.assertEqual(self.client.post("/listing/25/hide").status_code, 400)
        self.token("/search")
        self.post("/listing/25/hide")
        self.assertNotIn('id="listing-25"', self.client.get("/search?q=Honda").text)
        self.assertIn("2007 Honda Pilot", self.client.get("/hidden").text)
        self.post("/listing/25/unhide")
        self.assertIn('id="listing-25"', self.client.get("/search?q=Honda").text)

    def test_account_ownership_and_safe_redirect(self):
        self.login()
        self.post("/listing/2/save", next="https://evil.invalid/")
        with site.app.app_context():
            self.assertEqual(
                site.SavedListing.query.filter_by(user_id=1, listing_id=2).count(), 1
            )
        self.assertFalse(
            self.post("/listing/2/save", next="//evil.invalid").location.startswith(
                "//"
            )
        )
        self.assertEqual(self.post("/posting/1/delete").status_code, 403)
        self.post("/logout")
        self.assertEqual(self.client.get("/account").status_code, 302)

    def test_reply_identity_and_empty_reply(self):
        self.login()
        self.post(
            "/reply/24",
            body="Weekend pickup?",
            name="Mallory",
            email="mallory@example.test",
        )
        self.post("/reply/24", body=" ")
        with site.app.app_context():
            rows = site.Message.query.filter_by(listing_id=24).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                (rows[0].user_id, rows[0].sender_email, rows[0].direction),
                (1, "alice.j@test.com", "outbound"),
            )

    def test_post_duplicate_titles_and_delete(self):
        self.login()
        for _ in range(2):
            self.post(
                "/post",
                category_slug="bikes",
                title="Blue commuter bike",
                description="Rear rack",
                price="325",
                area="east bay",
                neighborhood="Oakland",
            )
        with site.app.app_context():
            posts = site.Listing.query.filter_by(owner_id=1).all()
            self.assertEqual(len(posts), 2)
            self.assertNotEqual(posts[0].slug, posts[1].slug)
            lid, slug = posts[0].id, posts[0].slug
        self.post(f"/posting/{lid}/delete")
        self.assertEqual(self.client.get(f"/d/{slug}/{lid}.html").status_code, 404)


if __name__ == "__main__":
    unittest.main()
