"""Behavioral regressions; use an isolated database and synthetic fixtures."""
import importlib
from datetime import datetime
import os
import re
from pathlib import Path
import sys
import tempfile
import unittest
from flask.testing import FlaskClient

SITE = Path(__file__).resolve().parents[1]
TEST_DIR = tempfile.TemporaryDirectory(prefix="discogs-tests-")
os.environ["DISCOGS_INSTANCE_DIR"] = TEST_DIR.name
os.environ["DISCOGS_SKIP_SEED"] = "1"
sys.path.insert(0, str(SITE))
m = importlib.import_module("app")


class IsolatedClient(FlaskClient):
    def open(self, *args, **kwargs):
        # Keep request-local login state separate from the fixture's DB context.
        with m.app.app_context():
            return super().open(*args, **kwargs)


m.app.test_client_class = IsolatedClient


class AppTests(unittest.TestCase):
    def setUp(self):
        m.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = m.app.app_context()
        self.context.push()
        self.reset_fixtures()

    def reset_fixtures(self):
        m.db.session.rollback()
        m.db.session.remove()
        m.db.drop_all()
        m.db.create_all()
        password = m.bcrypt.generate_password_hash("test-pass").decode()
        m.db.session.add_all([
            m.User(id=1, username="alice", email="alice@example.com", password_hash=password),
            m.User(id=2, username="bob", email="bob@example.com", password_hash=password),
            m.Artist(id=1, name="Bob Marley", slug="bob-marley"),
            m.Artist(id=2, name="Ziggy Marley", slug="ziggy-marley"),
            m.Label(id=1, name="Example Records", slug="example"),
            m.Genre(id=1, name="Reggae", slug="reggae"),
            m.Style(id=1, name="Dub", slug="dub"),
        ])
        m.db.session.flush()
        m.db.session.add_all([
            m.Release(id=1, discogs_id=1001, artist_id=1, title="Studio Session", have_count=10),
            m.Release(id=2, discogs_id=1002, artist_id=2, title="Another Session", have_count=100),
            m.List(id=1, user_id=1, title="Public selection", is_public=True),
            m.List(id=2, user_id=1, title="Private selection", description="Private notes", is_public=False),
            m.Forum(id=1, name="General Discussion", slug="general"),
            m.Forum(id=2, name="Help & Feedback", slug="help"),
            m.Thread(id=1, forum_id=1, user_id=1, title="Listening notes"),
        ])
        m.db.session.commit()
        self.client = m.app.test_client()

    def tearDown(self):
        m.db.session.remove()
        self.context.pop()

    def login(self, username="alice", target=None):
        return self.client.post("/login", query_string={"next": target} if target else {},
                                data={"username": username, "password": "test-pass"})

    def test_catalog_and_marketplace_pagination_preserves_filters(self):
        from urllib.parse import parse_qs, urlsplit
        import html
        for i in range(3, 70):
            m.db.session.add(m.Release(id=i, discogs_id=1000+i, artist_id=1,
                                      title=f"Studio Session {i}"))
            m.db.session.add(m.Listing(user_id=1, release_id=i, currency='GBP',
                                      price=i, status='For Sale', media_condition='Near Mint (NM or M-)'))
        m.db.session.commit()
        for route, params, selector in [
            ('/search', {'q':'Studio', 'type':'release'}, r'href="([^"]+)" aria-label="(?:Next|Previous) page"'),
            ('/marketplace', {'currency':'GBP', 'media':'Near Mint (NM or M-)', 'sort':'price_asc'}, r'href="([^"]+)">(?:Next|Prev)</a>'),
        ]:
            for page in (1, 2, 3, 999):
                with self.subTest(route=route, page=page):
                    response = self.client.get(route, query_string={**params,'page':page})
                    self.assertEqual(200, response.status_code)
                    links = re.findall(selector, response.get_data(as_text=True))
                    self.assertTrue(links)
                    for href in links:
                        query = parse_qs(urlsplit(html.unescape(href)).query)
                        self.assertEqual(1, len(query['page']))
                        for key, value in params.items(): self.assertEqual([value], query[key])
                        self.assertEqual(200, self.client.get(html.unescape(href)).status_code)

    def test_source_notes_render_as_escaped_plain_text(self):
        r = m.db.session.get(m.Release, 1)
        r.notes = '[url=https://www.discogs.com/label/1]Example[/url] [l=Example Records] [r1002] [b]Bold[/b] <script>alert(1)</script>'
        m.db.session.commit()
        body = self.client.get('/release/1001').get_data(as_text=True)
        self.assertIn('Example Example Records Another Session Bold &lt;script&gt;', body)
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertNotIn('[url=', body)

    def listing(self, **overrides):
        data = {"release_id": "1001", "price": "42.00", "currency": "USD",
                "media_condition": "Very Good Plus (VG+)",
                "sleeve_condition": "Very Good Plus (VG+)", "shipping_from": "United Kingdom"}
        data.update(overrides)
        return self.client.post("/sell", data=data)

    def test_private_lists_are_visible_only_to_owner(self):
        for identity in (None, "bob", "alice"):
            with self.subTest(identity=identity):
                self.client = m.app.test_client()
                if identity:
                    self.login(identity)
                html = self.client.get("/user/alice/lists").get_data(as_text=True)
                self.assertIn("Public selection", html)
                self.assertEqual("Private selection" in html, identity == "alice")
                self.assertEqual("Private notes" in html, identity == "alice")
                self.assertEqual(self.client.get("/list/2").status_code, 200 if identity == "alice" else 403)

    def test_other_user_cannot_add_to_private_list(self):
        self.login("bob")
        self.assertEqual(self.client.post("/list/2/add", data={"release_id": 1}).status_code, 403)
        self.assertEqual(m.ListItem.query.count(), 0)

    def test_list_add_accepts_visible_discogs_release_id(self):
        self.login()
        response = self.client.post(
            "/list/1/add",
            data={"release_id": 1002, "comment": "The edition shown in the release URL."},
        )
        self.assertEqual(response.status_code, 302)
        item = m.ListItem.query.one()
        self.assertEqual((item.list_id, item.release_id, item.comment),
                         (1, 2, "The edition shown in the release URL."))

    def test_review_for_missing_release_has_no_side_effect(self):
        self.login()
        response = self.client.post("/review", data={"release_id": 999999, "body": "Must not persist"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(m.Review.query.count(), 0)

    def test_invalid_sale_values_do_not_change_database(self):
        cases = [{"price": value} for value in ("-1", "0", "nan", "inf", "1e309", "1.001", "999999999999")]
        cases += [{"currency": "ZZZ"}, {"media_condition": "invented"},
                  {"sleeve_condition": "invented"}, {"shipping_from": ""}]
        for data in cases:
            with self.subTest(data=data):
                self.reset_fixtures()
                self.login()
                response = self.listing(**data)
                self.assertLess(response.status_code, 500)
                self.assertEqual(m.Listing.query.count(), 0)
                self.assertFalse(m.db.session.get(m.User, 1).is_seller)
                self.assertEqual(m.db.session.get(m.Release, 1).num_for_sale, 0)

    def test_valid_sale_has_bound_release_and_currency(self):
        self.login()
        response = self.listing(currency="GBP")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/marketplace?currency=GBP&sort=newest")
        row = m.Listing.query.one()
        self.assertEqual((row.user_id, row.release_id, row.price, row.currency), (1, 1, 42, "GBP"))
        self.assertTrue(m.db.session.get(m.User, 1).is_seller)

    def test_marketplace_price_sort_is_scoped_to_one_currency(self):
        m.db.session.add_all([
            m.Listing(user_id=1, release_id=1, price=10, currency="USD", shipping_from="US"),
            m.Listing(user_id=2, release_id=2, price=1, currency="GBP", shipping_from="UK"),
        ])
        m.db.session.commit()
        usd = self.client.get("/marketplace?sort=price_asc").get_data(as_text=True)
        self.assertIn("USD 10.00", usd)
        self.assertNotIn("GBP 1.00", usd)
        gbp = self.client.get("/marketplace?sort=price_asc&currency=GBP").get_data(as_text=True)
        self.assertIn("GBP 1.00", gbp)
        self.assertNotIn("USD 10.00", gbp)

    def test_login_rejects_foreign_or_ambiguous_returns(self):
        for target in ("https://foreign.invalid/", "//foreign.invalid/", "/\\foreign.invalid/",
                       "javascript:alert(1)", " https://foreign.invalid/", "/%5cforeign.invalid/"):
            with self.subTest(target=target):
                self.client = m.app.test_client()
                self.assertEqual(self.login(target=target).location, "/")

    def test_login_preserves_local_return(self):
        self.assertEqual(self.login(target="/list/1?view=items").location, "/list/1?view=items")

    def test_contextual_login_links_preserve_the_current_page(self):
        release = self.client.get("/release/1001").get_data(as_text=True)
        thread = self.client.get("/thread/1").get_data(as_text=True)
        self.assertIn('href="/login?next=/release/1001"', release)
        self.assertIn('href="/login?next=/thread/1"', thread)
        self.assertNotIn('href="/login"', release)
        self.assertNotIn('href="/login"', thread)

    def test_overlong_login_password_is_rejected_without_server_error(self):
        response = self.client.post("/login", data={"username": "alice", "password": "a" * 73})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid credentials", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/settings").status_code, 302)

    def test_mutations_ignore_foreign_referrer(self):
        self.login()
        response = self.client.post("/collection/add", data={"release_id": 1},
                                    headers={"Referer": "https://foreign.invalid/"})
        self.assertEqual(response.location, "/release/1001")

    def test_logout_requires_post_and_csrf(self):
        self.login()
        self.assertEqual(self.client.get("/logout").status_code, 405)
        m.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.client.post("/logout").status_code, 400)
        self.assertEqual(self.client.get("/settings").status_code, 200)

    def test_invalid_pages_do_not_crash(self):
        for route in ("/search", "/marketplace", "/lists", "/user/alice/collection", "/user/alice/wantlist"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route, query_string={"page": "oops"}).status_code, 200)

    def test_empty_entity_browse_is_populated(self):
        self.assertIn("Bob Marley", self.client.get("/search?type=artist").get_data(as_text=True))
        self.assertIn("Example Records", self.client.get("/search?type=label").get_data(as_text=True))

    def test_homepage_mirrors_live_sections_with_local_media(self):
        m.db.session.add_all([
            m.Listing(user_id=1, release_id=1, price=10, currency="USD", shipping_from="US"),
            m.Listing(user_id=2, release_id=2, price=900, currency="USD", shipping_from="US"),
            m.Listing(user_id=2, release_id=2, price=5, currency="GBP", shipping_from="UK"),
        ])
        m.db.session.get(m.Release, 1).num_for_sale = 1
        m.db.session.get(m.Release, 1).lowest_price = 10
        m.db.session.get(m.Release, 2).num_for_sale = 1
        m.db.session.get(m.Release, 2).lowest_price = 900
        m.db.session.commit()
        html = self.client.get("/").get_data(as_text=True)
        for title in ("This Week’s Best-Selling Vinyl Records &amp; CDs",
                      "This Week’s Most Valuable Vinyl Records &amp; CDs",
                      "This Week’s Most Collected Vinyl Records &amp; CDs"):
            self.assertIn(title, html)
        self.assertIn("1 copy from $900.00", html)
        self.assertIn('class="rc-btn rc-prev"', html)
        self.assertIn('class="rc-btn rc-next"', html)
        self.assertIn("/static/external_cache/homepage/phone-hands.png", html)
        self.assertNotIn("https://www.discogs.com/images/app/", html)
        # Most Valuable ranks by the highest USD asking price, not the GBP listing.
        valuable = m.most_valuable_releases()
        self.assertEqual([row.id for row in valuable], [2, 1])

    def _local_links(self, html, container_class):
        from html.parser import HTMLParser

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = None
                self.hrefs = []

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                classes = (values.get("class") or "").split()
                if self.depth is None and container_class in classes:
                    self.depth = 0
                if self.depth is not None:
                    if tag == "a" and values.get("href"):
                        self.hrefs.append(values["href"])
                    if tag not in ("img", "input", "br", "meta", "link", "path"):
                        self.depth += 1

            def handle_endtag(self, tag):
                if self.depth is not None and tag not in ("img", "input", "br", "meta", "link", "path"):
                    self.depth -= 1
                    if self.depth <= 0:
                        self.depth = None

        parser = Links()
        parser.feed(html)
        return parser.hrefs

    def test_header_and_footer_targets_are_local_and_resolve(self):
        html = self.client.get("/").get_data(as_text=True)
        hrefs = self._local_links(html, "site-header") + self._local_links(html, "site-footer")
        self.assertGreater(len(hrefs), 40)
        for href in hrefs:
            with self.subTest(href=href):
                self.assertFalse(href.startswith(("http://", "https://", "//")), href)
                if href.startswith("#"):
                    continue
                path = href.split("#")[0]
                status = self.client.get(path).status_code
                self.assertIn(status, (200, 302), (href, status))
        for label in ("Explore Discography", "Shop Music", "Sell Music", "Community", "Digs",
                      "Advanced Search", "Shop My Wants", "List Explorer", "Monthly Leaderboard",
                      "Help &amp; Resources", "Keyboard Shortcuts", "Cookie Settings", "Impressum",
                      "Sign Up / Log In"):
            self.assertIn(label, html)

    def test_menus_and_logout_do_not_depend_on_javascript(self):
        # Menus are native <details>, so every destination is in the DOM and reachable
        # by clicking the summary even if site.js never runs.
        self.login()
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("<details class=\"hdr-dd", html)
        self.assertIn("<summary class=\"hdr-dd-btn", html)
        self.assertNotIn("hdr-dd-btn\" aria-haspopup=\"true\" aria-expanded", html)
        self.assertIn('action="/logout"', html)
        self.assertIn("Log Out", html)
        self.assertIn("/user/alice/collection", html)
        self.assertEqual(self.client.post("/logout").status_code, 302)
        self.assertIn("Sign Up / Log In", self.client.get("/").get_data(as_text=True))

    def test_marketplace_format_filter_matches_live_parameter(self):
        vinyl = m.Format(id=1, name="Vinyl", slug="vinyl")
        cd = m.Format(id=2, name="CD", slug="cd")
        m.db.session.add_all([vinyl, cd])
        first, second = m.db.session.get(m.Release, 1), m.db.session.get(m.Release, 2)
        first.formats.append(vinyl)
        second.formats.append(cd)
        m.db.session.add_all([
            m.Listing(user_id=1, release_id=1, price=10, currency="USD", shipping_from="US"),
            m.Listing(user_id=2, release_id=2, price=20, currency="USD", shipping_from="US"),
        ])
        m.db.session.commit()
        html = self.client.get("/marketplace?format=Vinyl").get_data(as_text=True)
        self.assertIn("USD 10.00", html)
        self.assertNotIn("USD 20.00", html)
        html = self.client.get("/marketplace?format=cd").get_data(as_text=True)
        self.assertIn("USD 20.00", html)
        self.assertNotIn("USD 10.00", html)

    def test_shop_my_wants_requires_login_and_scopes_to_wantlist(self):
        m.db.session.add_all([
            m.WantlistItem(user_id=1, release_id=2),
            m.Listing(user_id=2, release_id=1, price=10, currency="USD", shipping_from="US"),
            m.Listing(user_id=2, release_id=2, price=20, currency="USD", shipping_from="US"),
        ])
        m.db.session.commit()
        self.assertEqual(self.client.get("/shop/mywants").status_code, 302)
        self.login()
        html = self.client.get("/shop/mywants").get_data(as_text=True)
        self.assertIn("Shop My Wants", html)
        self.assertIn("USD 20.00", html)
        self.assertNotIn("USD 10.00", html)

    def test_marketplace_sidebar_facets_and_price_range(self):
        m.db.session.add_all([
            m.Listing(user_id=1, release_id=1, price=7.5, currency="USD", shipping_from="Germany"),
            m.Listing(user_id=2, release_id=2, price=25, currency="USD", shipping_from="UK"),
        ])
        m.db.session.commit()
        html = self.client.get("/marketplace?media=Very+Good+Plus+%28VG%2B%29").get_data(as_text=True)
        for label in ("You Selected:", "Media Condition: Very Good Plus (VG+)", "Ships From", "Price Range",
                      "Shop Very Good Plus (VG+) Vinyl Records, CDs, and More in USD", "View Release Page",
                      "Add to Cart", "1 – 2 of 2"):
            self.assertIn(label, html)
        narrowed = self.client.get("/marketplace?price_min=5&price_max=10").get_data(as_text=True)
        self.assertIn("USD 7.50", narrowed)
        self.assertNotIn("USD 25.00", narrowed)
        shipped = self.client.get("/marketplace?ships_from=UK").get_data(as_text=True)
        self.assertIn("USD 25.00", shipped)
        self.assertNotIn("USD 7.50", shipped)
        searched = self.client.get("/marketplace?q=Another").get_data(as_text=True)
        self.assertIn("USD 25.00", searched)
        self.assertNotIn("USD 7.50", searched)

    def test_lists_page_searches_titles_and_keeps_owner_column(self):
        html = self.client.get("/lists?q=Public").get_data(as_text=True)
        self.assertIn("Public selection", html)
        self.assertNotIn("Private selection", html)
        self.assertIn("Recent Lists", html)
        self.assertIn("Search Lists", html)
        self.assertIn(">alice<", html)

    def test_forum_recent_search_and_thread_layout(self):
        recent = self.client.get("/forum/recent").get_data(as_text=True)
        self.assertIn("Listening notes", recent)
        self.assertIn("Recent Thread Activity", recent)
        self.assertIn("Listening notes", self.client.get("/forum/search?query=Listening").get_data(as_text=True))
        self.assertIn("No threads to show", self.client.get("/forum/search?query=zzz-nothing").get_data(as_text=True))
        self.assertEqual(self.client.get("/forum/posted").status_code, 302)
        index = self.client.get("/forum").get_data(as_text=True)
        self.assertIn("Your place to talk about music", index)
        self.assertIn("1 threads", index)
        thread = self.client.get("/thread/1").get_data(as_text=True)
        self.assertIn("General Discussion", thread)
        self.assertIn("You must be logged in to post.", thread)
        self.login()
        self.assertIn("Post reply", self.client.get("/thread/1").get_data(as_text=True))

    def test_auth_pages_mirror_live_copy_and_keep_field_names(self):
        login = self.client.get("/login").get_data(as_text=True)
        for text in ("Log in to Discogs to continue", "Forgot password?", 'name="username"', 'name="password"', "Sign up"):
            self.assertIn(text, login)
        register = self.client.get("/register").get_data(as_text=True)
        for text in ("Sign up to Discogs to continue", 'name="username"', 'name="email"', 'name="password"', 'name="location"'):
            self.assertIn(text, register)

    def test_release_page_shows_live_sections_and_keeps_action_forms(self):
        html = self.client.get("/release/1001").get_data(as_text=True)
        for text in ("[r1001]", "Statistics", "Have:", "Want:", "Add to Collection", "Add to Wantlist", "Sell a copy"):
            self.assertIn(text, html)
        self.login()
        html = self.client.get("/release/1001").get_data(as_text=True)
        self.assertIn('action="/collection/add"', html)
        self.assertIn('name="folder"', html)
        self.assertIn('action="/wantlist/add"', html)
        self.assertIn('action="/rate"', html)
        self.assertIn('action="/review"', html)

    def test_advanced_search_filters_by_label_and_catalog_number(self):
        release = m.db.session.get(m.Release, 1)
        release.labels.append(m.db.session.get(m.Label, 1))
        release.catno = "RS 9242"
        m.db.session.commit()
        page = self.client.get("/search/advanced").get_data(as_text=True)
        self.assertIn('action="/search"', page)
        self.assertEqual([row.id for row in m.search_releases("", label="Example").items], [1])
        self.assertEqual([row.id for row in m.search_releases("", catno="9242").items], [1])
        self.assertEqual([row.id for row in m.search_releases("", catno="0000").items], [])
        self.assertEqual(self.client.get("/search?label=Example&type=all").status_code, 200)

    def test_relevance_prefers_full_token_match_over_popularity(self):
        results = m.search_releases("Bob Marley").items
        self.assertEqual([row.id for row in results], [1, 2])

    def test_newest_sort_uses_the_source_addition_date(self):
        m.db.session.get(m.Release, 1).added_at = datetime(2025, 1, 1)
        m.db.session.get(m.Release, 2).added_at = datetime(2024, 1, 1)
        m.db.session.commit()
        results = m.search_releases("", sort="newest").items
        self.assertEqual([row.id for row in results], [1, 2])

    def test_facets_preserve_other_filters(self):
        # Facets now list only values present in the result set (live behaviour), so give
        # the matching release the genre/style/year the query asks for.
        release = m.db.session.get(m.Release, 1)
        release.year = 1978
        release.genres.append(m.db.session.get(m.Genre, 1))
        release.styles.append(m.db.session.get(m.Style, 1))
        m.db.session.commit()
        html = self.client.get("/search?q=Bob&genre=reggae&year=1978").get_data(as_text=True)
        self.assertIn("Search results for Bob", html)
        self.assertIn("Release (1)", html)
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []

            def handle_starttag(self, tag, attrs):
                if tag in ("a", "option"):
                    values = dict(attrs)
                    self.urls.append(values.get("href", values.get("value", "")))

        links = Links()
        links.feed(html)
        choices = [parse_qs(urlsplit(url).query) for url in links.urls if "style=dub" in url]
        self.assertTrue(choices)
        self.assertEqual(choices[0].get("genre"), ["reggae"])
        self.assertEqual(choices[0].get("year"), ["1978"])

    def test_collection_validation_and_duplicate_add_are_atomic(self):
        self.login()
        for field, value in (("folder", "invalid"), ("media_condition", "invalid"), ("sleeve_condition", "invalid")):
            self.client.post("/collection/add", data={"release_id": 1, field: value})
            self.assertEqual(m.CollectionItem.query.count(), 0)
            self.assertEqual(m.db.session.get(m.Release, 1).have_count, 10)
        for _ in range(2):
            self.client.post("/collection/add", data={"release_id": 1, "folder": "Vinyl"})
        self.assertEqual(m.CollectionItem.query.count(), 1)
        self.assertEqual(m.db.session.get(m.Release, 1).have_count, 11)

    def test_wantlist_rejects_unknown_grade(self):
        self.login()
        self.client.post("/wantlist/add", data={"release_id": 1, "min_grade": "invalid"})
        self.assertEqual(m.WantlistItem.query.count(), 0)

    def test_registration_rejects_invalid_identity_and_overlong_password(self):
        for overrides in ({"email": "@"}, {"username": "../escape"}, {"password": "a" * 73}):
            with self.subTest(overrides=overrides):
                self.reset_fixtures()
                data = {"username": "new_user", "email": "new@example.com", "password": "test-pass"}
                data.update(overrides)
                response = self.client.post("/register", data=data)
                self.assertLess(response.status_code, 500)
                self.assertEqual(m.User.query.count(), 2)

    def test_all_is_not_a_writable_collection_folder(self):
        """"All" is the unfiltered view, not a folder. While it sat in the folder enum it
        was offered in the form, accepted by the write path, and then unreachable: the
        collection list treats folder == "All" as "do not filter", so such a row could
        never be viewed as a folder again."""
        self.assertNotIn("All", m.COLLECTION_FOLDERS)
        self.assertEqual("All", m.UNFILTERED_FOLDER)
        self.login("alice")
        page = self.client.get("/release/1001").get_data(as_text=True)
        select = re.search(r'<select[^>]*name="folder"[^>]*>(.*?)</select>', page, re.S)
        self.assertIsNotNone(select)
        self.assertNotIn(">All<", select.group(1))
        self.client.post("/collection/add", data={
            "release_id": 1, "folder": "All",
            "media_condition": "Near Mint (NM or M-)",
            "sleeve_condition": "Near Mint (NM or M-)"}, follow_redirects=True)
        self.assertEqual(0, m.CollectionItem.query.count(),
                         "a rejected folder must not write a collection row")

    def test_collection_tab_row_lists_all_exactly_once(self):
        self.login("alice")
        page = self.client.get("/user/alice/collection").get_data(as_text=True)
        tabs = re.findall(r'folder=([^"&]+)"', page)
        self.assertEqual(1, tabs.count("All"), f"tabs={tabs}")

    def test_relative_time_matches_live_singular_and_plural(self):
        """Live Discogs writes "1 day ago" and "12 minutes ago"; every unit here was
        hard-coded plural and the minute unit was abbreviated to "min"."""
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        for delta, expected in [
            (timedelta(minutes=1), "1 minute ago"), (timedelta(minutes=12), "12 minutes ago"),
            (timedelta(hours=1), "1 hour ago"), (timedelta(hours=11), "11 hours ago"),
            (timedelta(days=1), "1 day ago"), (timedelta(days=10), "10 days ago"),
            (timedelta(days=40), "1 month ago"), (timedelta(days=400), "1 year ago"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(expected, m.relative_time(now - delta))


if __name__ == "__main__":
    unittest.main()
