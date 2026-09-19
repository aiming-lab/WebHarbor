"""Regression tests for issue #13 user-visible URL realism."""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from flask import Flask, request as flask_request


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_url_realism  # noqa: E402


def _load_functions(path: Path, names: tuple[str, ...], extra_globals=None):
    tree = ast.parse(path.read_text())
    wanted = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    missing = set(names) - {node.name for node in wanted}
    if missing:
        raise AssertionError(f"{path} missing functions: {sorted(missing)}")
    module = ast.Module(body=wanted, type_ignores=[])
    code = compile(module, str(path), "exec")
    ns = {"url_for": lambda endpoint: f"/{endpoint}", "request": flask_request}
    if extra_globals:
        ns.update(extra_globals)
    exec(code, ns)
    return ns


class SourceGuardTests(unittest.TestCase):
    def test_static_url_realism_checker(self):
        self.assertFalse(check_url_realism.check_forbidden())
        self.assertFalse(check_url_realism.check_required())
        self.assertFalse(check_url_realism.check_relative_next_templates())


class RedirectHelperTests(unittest.TestCase):
    def setUp(self):
        self.flask = Flask(__name__)
        self.allrecipes = _load_functions(
            ROOT / "sites/allrecipes/app.py",
            ("current_relative_url", "safe_redirect_target"),
        )
        self.booking = _load_functions(
            ROOT / "sites/booking/app.py",
            ("current_relative_url", "safe_redirect_target"),
        )

    def test_relative_next_keeps_path_and_query(self):
        with self.flask.test_request_context("/recipe/waffles?servings=6"):
            self.assertEqual(
                self.allrecipes["current_relative_url"](),
                "/recipe/waffles?servings=6",
            )
        with self.flask.test_request_context("/stays?q=paris"):
            self.assertEqual(self.booking["current_relative_url"](), "/stays?q=paris")

    def test_safe_redirect_rejects_absolute_and_protocol_relative(self):
        with self.flask.test_request_context("/"):
            for helpers in (self.allrecipes, self.booking):
                safe = helpers["safe_redirect_target"]
                self.assertEqual(safe("/stays"), "/stays")
                self.assertEqual(safe("/recipe/waffles?x=1"), "/recipe/waffles?x=1")
                self.assertEqual(safe("http://localhost:40005/stays"), "/index")
                self.assertEqual(safe("https://evil.example/phish"), "/index")
                self.assertEqual(safe("//evil.example/phish"), "/index")
                self.assertEqual(safe(None, "saved"), "/saved")


class BbcShareUrlTests(unittest.TestCase):
    def test_prefers_source_url_then_bbc_fallback(self):
        ns = _load_functions(
            ROOT / "sites/bbc_news/app.py",
            ("bbc_article_share_url",),
        )
        share = ns["bbc_article_share_url"]
        with_source = types.SimpleNamespace(
            source_url="https://www.bbc.com/news/articles/c9w7g8x2y1z0",
            slug="c9w7g8x2y1z0",
        )
        self.assertEqual(share(with_source), with_source.source_url)
        fallback = types.SimpleNamespace(source_url="", slug="c-fallback")
        self.assertEqual(
            share(fallback),
            "https://www.bbc.com/news/articles/c-fallback",
        )


class GithubHostRecoveryTests(unittest.TestCase):
    def test_external_github_host_detection(self):
        ns = _load_functions(
            ROOT / "sites/github/app.py",
            ("is_external_github_host",),
        )
        detect = ns["is_external_github_host"]
        self.assertTrue(detect("github.com"))
        self.assertTrue(detect("GITHUB.COM:443"))
        self.assertFalse(detect("localhost:40006"))
        self.assertFalse(detect("127.0.0.1:40006"))
        self.assertFalse(detect("127.0.0.1"))


class GoogleMapRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site_dir = ROOT / "sites/google_map"
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        os.environ.setdefault("WTF_CSRF_ENABLED", "0")
        sys.path.insert(0, str(site_dir))
        spec = importlib.util.spec_from_file_location(
            "google_map_app", site_dir / "app.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.mod = module
        module.app.root_path = str(site_dir)
        module.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{cls._tmp.name}",
        )
        # Flask-SQLAlchemy 3 binds engines during the first init_app; changing
        # the URI later is ignored unless the extension is re-registered.
        module.app.extensions.pop("sqlalchemy", None)
        module.db.init_app(module.app)
        with module.app.app_context():
            module.db.session.remove()
            module.db.drop_all()
            module.db.create_all()
            city = module.City(
                slug="milan",
                display_name="Milan",
                country="Italy",
            )
            cat = module.Category(slug="attractions", name="Attractions")
            module.db.session.add_all([city, cat])
            module.db.session.flush()
            place = module.Place(
                slug="galleria-vittorio-emanuele",
                name="Galleria Vittorio Emanuele II",
                category_id=cat.id,
                city_id=city.id,
                website="https://example.com/galleria-vittorio-emanuele",
                rating=4.7,
                review_count=1200,
                hours="Mon-Sun: 9:00 AM - 6:00 PM",
                photos_json="[]",
            )
            module.db.session.add(place)
            module.db.session.commit()
        cls.client = module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.mod.app.app_context():
            cls.mod.db.session.remove()
            cls.mod.db.engine.dispose()
        Path(cls._tmp.name).unlink(missing_ok=True)

    def test_share_box_uses_google_maps_url(self):
        response = self.client.get("/place/galleria-vittorio-emanuele")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(
            "https://www.google.com/maps/place/Galleria+Vittorio+Emanuele+II+Milan/",
            body,
        )
        self.assertNotIn("localhost:40008", body)
        self.assertNotIn("example.com/galleria-vittorio-emanuele", body)

    def test_placeholder_website_falls_back_to_maps_url(self):
        with self.mod.app.app_context():
            place = self.mod.Place.query.filter_by(
                slug="galleria-vittorio-emanuele"
            ).one()
            self.assertEqual(
                self.mod.display_place_website(place),
                self.mod.google_maps_place_url(place),
            )
            place.website = "https://www.galleriavittorioemanuele.it/"
            self.assertEqual(
                self.mod.display_place_website(place),
                "https://www.galleriavittorioemanuele.it/",
            )


if __name__ == "__main__":
    unittest.main()
