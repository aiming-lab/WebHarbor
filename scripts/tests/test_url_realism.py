"""Regression tests for issue #13 user-visible URL realism."""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
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

    def test_no_site_leaks_the_mirror_address(self):
        self.assertFalse(check_url_realism.check_sitewide())


class SitewideScanTests(unittest.TestCase):
    """The site-wide scan flags the leak patterns and nothing else."""

    def _scan(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            return check_url_realism.scan_sites(root)

    def test_flags_absolute_request_urls_in_templates(self):
        found = self._scan({
            "sites/a/templates/x.html": '<input name="next" value="{{ request.url }}">\n'
                                        '{{ request.base_url }} {{ request.host_url }}\n'
                                        "{{ url_for('p', _external=True) }}\n",
        })
        self.assertEqual(
            [(rule, line) for rule, _, line, _ in found],
            [("template-request-url", 1), ("template-request-url", 2),
             ("template-external-url", 3)])

    def test_flags_absolute_next_and_share_links_in_python(self):
        found = self._scan({
            "sites/a/app.py": "redirect(url_for('login', next=request.url))\n"
                              "share_url = request.host_url.rstrip('/') + path\n"
                              "redirect(url_for('login', next=current_relative_url()))\n",
        })
        self.assertEqual([(rule, line) for rule, _, line, _ in found],
                         [("absolute-next", 1), ("share-from-host", 2)])

    def test_flags_clipboard_writes_of_the_mirror_location(self):
        found = self._scan({
            "sites/a/static/js/site.js": "navigator.clipboard.writeText(window.location.href);\n"
                                         "navigator.clipboard.writeText(location.origin + p);\n"
                                         "window.location.href = '/next';\n"
                                         "history.replaceState(null, '', location.href);\n",
        })
        self.assertEqual([(rule, line) for rule, _, line, _ in found],
                         [("clipboard-location", 1), ("clipboard-location", 2)])

    def test_ignores_lookalikes_and_non_site_code(self):
        found = self._scan({
            "sites/a/templates/x.html": "{{ request.url_rule }} {{ request.path }}\n",
            "sites/a/app.py": "origin = urlsplit(request.host_url)\nnext = request.path\n",
            "sites/a/static/js/x.min.js": "navigator.clipboard.writeText(location.href)",
            "sites/a/static/images/x.js": "navigator.clipboard.writeText(location.href)",
            "sites/a/verify/verify_1.py": "share_url = request.host_url\n",
            "sites/a/tests/test_x.py": "next=request.url\n",
        })
        self.assertEqual(found, [])

    def test_known_surfaces_are_allowed_and_stale_entries_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sites/a/templates").mkdir(parents=True)
            (root / "sites/a/templates/x.html").write_text("{{ request.base_url }}\n")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertTrue(check_url_realism.check_sitewide(root, known={}))
                self.assertIn("sites/a/templates/x.html:1", out.getvalue())
                known = {("sites/a/templates/x.html", "template-request-url"): "why"}
                self.assertFalse(check_url_realism.check_sitewide(root, known=known))
                known[("sites/a/templates/gone.html", "template-request-url")] = "why"
                self.assertTrue(check_url_realism.check_sitewide(root, known=known))
                self.assertIn("stale", out.getvalue())


class RelativeNextHelperTests(unittest.TestCase):
    """Sites that build login/return links from the current request."""

    SITES = ("berkeley", "nba", "samsung", "thumbtack", "re_max")

    def setUp(self):
        self.flask = Flask(__name__)
        self.helpers = {
            site: _load_functions(
                ROOT / f"sites/{site}/app.py", ("current_relative_url",),
                extra_globals={"url_quote": quote})
            for site in self.SITES
        }

    def test_current_relative_url_has_no_scheme_or_host(self):
        cases = [("/tickets?team=lakers", "/tickets?team=lakers"),
                 ("/projects/new?category=house-cleaning&pro=3", "/projects/new?category=house-cleaning&pro=3"),
                 ("/a%20b/c?q=why?", "/a%20b/c?q=why?"),
                 ("/news/x?", "/news/x")]
        for site, ns in self.helpers.items():
            for url, expected in cases:
                with self.flask.test_request_context(url, base_url="http://localhost:40999"):
                    self.assertEqual(ns["current_relative_url"](), expected, site)

    def test_re_max_redirect_target_is_same_site_only(self):
        ns = _load_functions(ROOT / "sites/re_max/app.py", ("safe_redirect_target",))
        safe = ns["safe_redirect_target"]
        self.assertEqual(safe("/tx/austin-real-estate?beds=2", "/x"), "/tx/austin-real-estate?beds=2")
        for target in (None, "", "advice", "//evil.example", "https://evil.example/",
                       "http://localhost:40096/account", "/\\evil.example",
                       "/%5cevil.example", "/%2fevil.example", "/a\tb", "/a%0d%0aX: y"):
            self.assertEqual(safe(target, "/x"), "/x", target)


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
