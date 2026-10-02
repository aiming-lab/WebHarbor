import hashlib
import html
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


SITE_DIR = Path(__file__).resolve().parents[1]
class FandomRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tempdir.name) / "fandom"
        shutil.copytree(SITE_DIR, cls.site, ignore=shutil.ignore_patterns(
            "instance", "__pycache__", "*.pyc"))
        shutil.copytree(cls.site / "instance_seed", cls.site / "instance")
        cls.old_cwd = Path.cwd()
        os.chdir(cls.site)
        sys.path.insert(0, str(cls.site))
        cls.module = importlib.import_module("app")
        cls.module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.app = cls.module.app
        with cls.app.app_context():
            cls.initial_wiki_count = cls.module.Wiki.query.count()
            cls.initial_article_count = cls.module.Article.query.count()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old_cwd)
        sys.path.remove(str(cls.site))
        sys.modules.pop("app", None)
        cls.tempdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, identity, password):
        return self.client.post(
            "/login",
            data={"email": identity, "password": password},
            follow_redirects=True,
        )

    def test_only_supported_content_is_discoverable(self):
        response = self.client.get("/")
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for name in ("Marvel Cinematic Universe Wiki", "Wookieepedia", "Genshin Impact Wiki"):
            self.assertIn(name, text)
        for name in ("Harry Potter Wiki", "A Wiki of Ice and Fire", "The One Wiki"):
            self.assertNotIn(name, text)

        response = self.client.get("/search?q=Tony")
        self.assertIn("Tony Stark", response.get_data(as_text=True))
        response = self.client.get("/search?q=Tony&wiki=unsupported")
        self.assertNotIn("Tony Stark", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/wiki/harrypotter/").status_code, 404)

        with self.app.app_context():
            empty = self.module.Article.query.filter(
                self.module.func.trim(
                    self.module.func.coalesce(self.module.Article.content, "")
                ) == ""
            ).count()
            self.assertEqual(empty, 0)
            self.assertEqual(self.initial_wiki_count, 3)
            self.assertEqual(self.initial_article_count, 182)

    def test_guest_auth_and_registration_flow(self):
        self.assertIn("Sign in", self.client.get("/").get_data(as_text=True))
        edit = self.client.get("/wiki/mcu/Tony_Stark/edit")
        self.assertEqual(edit.status_code, 302)
        self.assertIn("/login", edit.headers["Location"])

        response = self.client.post("/register", data={
            "email": "new.editor@example.com",
            "username": "NewEditor",
            "password": "StrongPass!42",
        }, follow_redirects=True)
        self.assertIn("NewEditor", response.get_data(as_text=True))
        response = self.client.get("/logout", follow_redirects=True)
        self.assertIn("Sign in", response.get_data(as_text=True))
        self.assertNotIn("NewEditor</a>", response.get_data(as_text=True))

    def test_article_rendering_uses_wikitext_body_once(self):
        response = self.client.get("/wiki/mcu/Tony_Stark")
        page = response.get_data(as_text=True)
        visible = html.unescape(re.sub(r"<[^>]+>", "", page))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("'''Iron Man'''", visible)
        self.assertNotIn("[[Avengers]]", visible)
        self.assertEqual(visible.count("(also known as Iron Man)"), 1)
        self.assertIn('href="/wiki/mcu/Avengers"', page)
        section_links = re.findall(
            r'class="edit-section"[^>]*href="([^"]+)"', page
        )
        self.assertGreater(len(section_links), 0)
        self.assertEqual(set(section_links), {"/wiki/mcu/Tony_Stark/edit"})
        guest = self.client.get(section_links[0])
        self.assertEqual(guest.status_code, 302)
        self.assertIn("/login", guest.headers["Location"])
        self.login("AliceJ", "MCU_Fan_Alice2024")
        editor = self.client.get(section_links[0])
        self.assertEqual(editor.status_code, 200)
        self.assertIn('name="content"', editor.get_data(as_text=True))

    def test_login_edit_history_categories_and_revision_delta(self):
        response = self.login("bob.k@test.com", "StarWars_Bob_42")
        self.assertIn("BobK", response.get_data(as_text=True))
        article_path = "/wiki/starwars/Luke_Skywalker"
        with self.app.app_context():
            article = self.module.Article.query.filter_by(
                wiki_id=2, slug="Luke_Skywalker").one()
            before = article.content
            before_size = len(before.encode("utf-8"))
            seeded_categories = {category.slug for category in article.categories}
            self.assertEqual(seeded_categories, {"Jedi", "Rebel_Alliance"})
        marker = "A focused regression-test note."
        new_content = before + "\n\n== Test note ==\n" + marker + \
            "\n[[Category:Bounty Hunters]]"
        response = self.client.post(article_path + "/edit", data={
            "content": new_content,
            "summary": "Regression edit",
        }, follow_redirects=True)
        self.assertIn(marker, response.get_data(as_text=True))
        self.assertNotIn("[[Category:Bounty Hunters]]",
                         response.get_data(as_text=True))
        history = self.client.get(article_path + "/history").get_data(as_text=True)
        self.assertIn("Regression edit", history)
        self.assertIn("BobK", history)
        category = self.client.get(
            "/wiki/starwars/Category:Bounty_Hunters"
        ).get_data(as_text=True)
        self.assertIn("Luke Skywalker", category)
        with self.app.app_context():
            revision = self.module.Revision.query.filter_by(
                summary="Regression edit"
            ).one()
            tagged_revision_id = revision.id
            self.assertEqual(revision.bytes_size, len(new_content.encode("utf-8")))
            self.assertEqual(revision.bytes_delta,
                             len(new_content.encode("utf-8")) - before_size)
            article = self.module.Article.query.filter_by(
                wiki_id=2, slug="Luke_Skywalker").one()
            self.assertEqual(
                {category.slug for category in article.categories},
                seeded_categories | {"Bounty_Hunters"},
            )

        response = self.client.post(article_path + "/edit", data={
            "content": before,
            "summary": "Remove test category",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        category = self.client.get(
            "/wiki/starwars/Category:Bounty_Hunters"
        ).get_data(as_text=True)
        self.assertNotIn("Luke Skywalker", category)
        with self.app.app_context():
            article = self.module.Article.query.filter_by(
                wiki_id=2, slug="Luke_Skywalker").one()
            self.assertEqual(
                {category.slug for category in article.categories},
                seeded_categories,
            )

        self.client.post(
            f"{article_path}/revert/{tagged_revision_id}",
            follow_redirects=True,
        )
        with self.app.app_context():
            article = self.module.Article.query.filter_by(
                wiki_id=2, slug="Luke_Skywalker").one()
            self.assertEqual(
                {category.slug for category in article.categories},
                seeded_categories | {"Bounty_Hunters"},
            )

    def test_article_prose_only_edit_preserves_seeded_categories(self):
        self.login("AliceJ", "MCU_Fan_Alice2024")
        for wiki_id, wiki_slug, article_slug, expected in (
            (1, "mcu", "Tony_Stark",
             {"Heroes", "Supporting_Characters", "Avengers"}),
            (2, "starwars", "Luke_Skywalker", {"Jedi", "Rebel_Alliance"}),
        ):
            with self.subTest(article=article_slug):
                with self.app.app_context():
                    article = self.module.Article.query.filter_by(
                        wiki_id=wiki_id, slug=article_slug
                    ).one()
                    content = article.content
                    self.assertNotIn("[[Category:", content)
                    self.assertEqual(
                        {category.slug for category in article.categories},
                        expected,
                    )
                self.client.post(
                    f"/wiki/{wiki_slug}/{article_slug}/edit",
                    data={
                        "content": content + "\n\nProse-only preservation check.",
                        "summary": "Prose-only edit",
                    },
                    follow_redirects=True,
                )
                with self.app.app_context():
                    article = self.module.Article.query.filter_by(
                        wiki_id=wiki_id, slug=article_slug
                    ).one()
                    self.assertEqual(
                        {category.slug for category in article.categories},
                        expected,
                    )

    def test_watch_toggle_updates_watchlist_and_account(self):
        self.login("AliceJ", "MCU_Fan_Alice2024")
        with self.app.app_context():
            article = self.module.Article.query.filter_by(
                wiki_id=1, slug="Thanos").one()
            existing = self.module.WatchItem.query.filter_by(
                user_id=self.module.User.query.filter_by(username="AliceJ").one().id,
                article_id=article.id,
            ).first()
            if existing:
                self.module.db.session.delete(existing)
                self.module.db.session.commit()
        response = self.client.post(
            "/wiki/mcu/Thanos/watch", follow_redirects=True)
        self.assertIn("watching", response.get_data(as_text=True).lower())
        watchlist = self.client.get("/wiki/mcu/Special:Watchlist")
        self.assertIn("Thanos", watchlist.get_data(as_text=True))
        self.assertIn("Thanos", self.client.get("/account").get_data(as_text=True))

        response = self.client.post(
            "/wiki/mcu/Thanos/watch", follow_redirects=True)
        self.assertIn("no longer watching", response.get_data(as_text=True).lower())
        self.assertNotIn(
            "Thanos", self.client.get("/wiki/mcu/Special:Watchlist").get_data(as_text=True)
        )
        self.assertNotIn("Thanos", self.client.get("/account").get_data(as_text=True))

    def test_discovery_navigation_uses_live_routes(self):
        page = self.client.get("/").get_data(as_text=True)
        for path in ("/games", "/movies", "/tv", "/explore"):
            with self.subTest(path=path):
                self.assertIn(f'href="{path}"', page)
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_file_attribution_only_links_existing_users(self):
        files_page = self.client.get("/wiki/mcu/Special:ListFiles")
        page = files_page.get_data(as_text=True)
        self.assertEqual(files_page.status_code, 200)
        self.assertIn("ShinyCelestia", page)
        self.assertNotIn('href="/user/ShinyCelestia"', page)
        self.assertIn('href="/user/AliceJ"', page)

        with self.app.app_context():
            historical = self.module.FileAsset.query.filter_by(
                wiki_id=1, uploader_label="ShinyCelestia"
            ).first()
            known = self.module.FileAsset.query.filter_by(
                wiki_id=1, uploader_label="AliceJ"
            ).first()
            self.assertIsNotNone(historical)
            self.assertIsNotNone(known)
            historical_path = (
                f"/wiki/mcu/File:{historical.filename}" if historical else ""
            )
            known_path = f"/wiki/mcu/File:{known.filename}" if known else ""

        historical_page = self.client.get(historical_path).get_data(as_text=True)
        self.assertIn("ShinyCelestia", historical_page)
        self.assertNotIn('href="/user/ShinyCelestia"', historical_page)
        self.assertIn(
            'href="/user/AliceJ"',
            self.client.get(known_path).get_data(as_text=True),
        )

    def test_authorship_only_links_existing_users(self):
        forum_index = self.client.get(
            "/wiki/mcu/Forum"
        ).get_data(as_text=True)
        self.assertIn("StarkFan42", forum_index)
        self.assertNotIn('href="/user/StarkFan42"', forum_index)
        self.assertIn('href="/user/AliceJ"', forum_index)

        thread = self.client.get(
            "/wiki/mcu/Forum/Thread/2"
        ).get_data(as_text=True)
        for historical_label in (
            "StarkFan42", "InfinityScribe", "EnabranTain", "ShinyCelestia"
        ):
            self.assertIn(historical_label, thread)
            self.assertNotIn(f'href="/user/{historical_label}"', thread)
        self.assertIn('href="/user/AliceJ"', thread)
        self.assertIn('href="/user/BobK"', thread)

        comments = self.client.get(
            "/wiki/mcu/Tony_Stark/comments"
        ).get_data(as_text=True)
        self.assertIn("InfinityScribe", comments)
        self.assertNotIn('href="/user/InfinityScribe"', comments)
        self.assertIn('href="/user/AliceJ"', comments)

        history = self.client.get(
            "/wiki/mcu/Tony_Stark/history"
        ).get_data(as_text=True)
        self.assertIn("LucasCanon", history)
        self.assertNotIn('href="/user/LucasCanon"', history)

    def test_new_article_revision_delta_starts_from_zero(self):
        self.login("BobK", "StarWars_Bob_42")
        content = "== Overview ==\n\nA newly created test page."
        response = self.client.post(
            "/wiki/starwars/Regression_Delta_Page/edit",
            data={"content": content, "summary": "Create regression page"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("A newly created test page.", response.get_data(as_text=True))
        with self.app.app_context():
            revision = self.module.Revision.query.filter_by(
                summary="Create regression page"
            ).one()
            self.assertEqual(revision.bytes_delta, len(content.encode("utf-8")))

    def test_tasks_have_basic_keys_and_live_targets(self):
        required = {"web_name", "id", "ques", "web", "upstream_url", "verifier_path", "judge_rubric"}
        tasks = [
            json.loads(line) for line in (self.site / "tasks.jsonl").read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(tasks), 18)
        self.assertEqual([task["id"] for task in tasks],
                         [f"Fandom--{i}" for i in range(18)])
        for task in tasks:
            self.assertEqual(set(task), required)
            self.assertEqual(task["web"], "http://localhost:40117/")

        targets = [
            "/wiki/mcu/Tony_Stark",
            "/wiki/mcu/Thanos",
            "/wiki/genshin/Zhongli",
            "/wiki/starwars/Mace_Windu",
            "/wiki/mcu/Category:Guardians_of_the_Galaxy",
            "/wiki/genshin/Category:Five-Star_Characters",
            "/wiki/starwars/Special:RecentChanges?hide_bot=1",
            "/wiki/genshin/Hu_Tao/history",
            "/wiki/starwars/Tatooine",
            "/wiki/mcu/Special:WhatLinksHere/Tony_Stark",
            "/wiki/mcu/Forum",
            "/wiki/genshin/Special:ListFiles?q=Mondstadt",
        ]
        for target in targets:
            with self.subTest(target=target):
                self.assertEqual(self.client.get(target).status_code, 200)

    def test_asset_manifest_and_references(self):
        manifest = json.loads((self.site / "asset_manifest.json").read_text())
        self.assertGreaterEqual(len(manifest["assets"]), 15)
        for asset in manifest["assets"]:
            path = self.site / asset["path"]
            self.assertTrue(path.is_file(), asset["path"])
            self.assertGreater(path.stat().st_size, 5000)
            self.assertTrue(asset["source_url"].startswith("https://"))
        page = self.client.get("/wiki/mcu/Tony_Stark").get_data(as_text=True)
        self.assertNotIn("production notes", page)
        self.assertNotIn("Official Marvel Cinematic Universe archive", page)
        self.assertIn("mcu_iron_man__film.jpg", page)

    def test_seed_schema_and_two_restored_boots_are_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            boot_site = Path(directory) / "fandom"
            shutil.copytree(self.site, boot_site, ignore=shutil.ignore_patterns(
                "instance", "__pycache__", "*.pyc"))
            seed = boot_site / "instance_seed" / "fandom.db"
            expected = hashlib.sha256(seed.read_bytes()).hexdigest()
            for _ in range(2):
                shutil.rmtree(boot_site / "instance", ignore_errors=True)
                shutil.copytree(boot_site / "instance_seed", boot_site / "instance")
                subprocess.run(
                    [sys.executable, "-c", "import app"],
                    cwd=boot_site,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                actual = hashlib.sha256(
                    (boot_site / "instance" / "fandom.db").read_bytes()
                ).hexdigest()
                self.assertEqual(actual, expected)

        import sqlite3
        con = sqlite3.connect(self.site / "instance_seed" / "fandom.db")
        indexes = {
            row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        self.assertTrue({
            "ix_articles_view_count",
            "ix_articles_wiki_slug",
            "ix_articles_wiki_view",
        }.issubset(indexes))

    def test_review_historical_revision_and_plain_excerpt(self):
        response = self.client.get('/wiki/mcu/Tony_Stark?oldid=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Historical revision', response.data)
        self.assertEqual(self.client.get('/wiki/mcu/Tony_Stark?oldid=999999').status_code, 404)
        self.assertEqual(self.module.wiki_excerpt("Read [[Tony_Stark|Tony Stark]]"), 'Read Tony Stark')
        self.assertIn(b'Category:Five-Star_Characters', self.client.get('/wiki/genshin/Special:Categories').data)

    def test_recent_changes_label_reports_rows_shown_and_page_limit(self):
        base = "/wiki/starwars/Special:RecentChanges"
        html = self.client.get(base + "?hide_bot=1").get_data(as_text=True)
        self.assertEqual(html.count('class="changes-row"'), 200)
        self.assertIn("200 revisions shown on Wookieepedia, newest first (page limit 200).", html)
        self.assertNotIn("Latest 200 edits", html)

        m = self.module
        with self.app.app_context():
            wiki = m.Wiki.query.filter_by(slug="genshin").one()
            expected = m.Revision.query.join(m.Article).filter(
                m.Article.wiki_id == wiki.id,
                m.Revision.minor.is_(False),
                m.Revision.bot.is_(False),
            ).count()
        self.assertLess(expected, 200)
        html = self.client.get(
            "/wiki/genshin/Special:RecentChanges?hide_minor=1&hide_bot=1"
        ).get_data(as_text=True)
        self.assertEqual(html.count('class="changes-row"'), expected)
        self.assertIn(
            f"{expected} revisions shown on {wiki.name}, newest first (page limit 200).",
            html,
        )


if __name__ == "__main__":
    unittest.main()
