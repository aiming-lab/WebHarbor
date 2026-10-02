"""Regression tests for issue #13 user-visible URL realism."""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from urllib.parse import quote, unquote, urlencode, urlsplit
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
    ns = {"url_for": lambda endpoint: f"/{endpoint}", "request": flask_request, "quote": quote, "unquote": unquote, "urlencode": urlencode, "urlsplit": urlsplit}
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
                for target in ('/\\evil.example', '/%5cevil.example', '/%2fevil.example', '/\tevil', '/a%0d%0aLocation:evil'):
                    self.assertEqual(safe(target), '/index')

    def test_relative_url_preserves_question_mark_query_and_encoded_path(self):
        for target, expected in [('/stays?q=why?', '/stays?q=why?'),
                                 ('/a%3Fb?q=x', '/a%3Fb?q=x'), ('/stays?', '/stays')]:
            with self.flask.test_request_context(target):
                for helpers in (self.allrecipes, self.booking):
                    self.assertEqual(helpers['current_relative_url'](), expected)


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
        self.assertIsNone(share(fallback))
        for source in ("https://evil.example/", "javascript:alert(1)", "http://localhost:40000/"):
            fallback.source_url = source
            self.assertIsNone(share(fallback))


class MapsLinkTests(unittest.TestCase):
    def test_maps_search_and_business_website_are_distinct(self):
        ns = _load_functions(ROOT / 'sites/google_map/app.py',
                             ('google_maps_place_url', 'display_place_website'))
        place = types.SimpleNamespace(name='A & B', city=types.SimpleNamespace(display_name='Milan'), website='https://example.com/a')
        self.assertEqual(ns['google_maps_place_url'](place),
                         'https://www.google.com/maps/search/?api=1&query=A+%26+B+Milan')
        self.assertIsNone(ns['display_place_website'](place))
        place.website = 'https://www.galleriavittorioemanuele.it/'
        self.assertEqual(ns['display_place_website'](place), place.website)
        for value in ('javascript:alert(1)', 'https://foo.example.com/', ''):
            place.website = value
            self.assertIsNone(ns['display_place_website'](place))


if __name__ == '__main__':
    unittest.main()
