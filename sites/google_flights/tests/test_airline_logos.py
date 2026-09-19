#!/usr/bin/env python3
"""Regression tests for Google Flights airline logo serving (issue #22)."""
import re
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SITE = Path(__file__).resolve().parents[1]
ICON_DIR = SITE / 'static' / 'icons' / 'airlines'
PNG_SIG = b'\x89PNG\r\n\x1a\n'
TEMPLATES = (
    SITE / 'templates' / 'flights.html',
    SITE / 'templates' / 'search.html',
    SITE / 'templates' / 'flight_detail.html',
)


def _airlines():
    sys.path.insert(0, str(SITE))
    from seed_data import AIRLINES
    return AIRLINES


def setUpModule():
    seed = SITE / 'instance_seed' / 'google_flights.db'
    if seed.is_file():
        instance = SITE / 'instance'
        instance.mkdir(exist_ok=True)
        shutil.copy2(seed, instance / 'google_flights.db')


class AirlineLogoFilesTest(unittest.TestCase):
    def test_every_seeded_airline_has_a_png(self):
        airlines = _airlines()
        self.assertEqual(len(airlines), 23)
        for name, code, slug in airlines:
            path = ICON_DIR / f'{code}.png'
            self.assertTrue(path.is_file(), f'missing {path} for {name} ({slug})')
            data = path.read_bytes()
            self.assertTrue(data.startswith(PNG_SIG), f'{path} is not a PNG')
            self.assertGreater(len(data), 100)

    def test_seed_data_points_at_git_tracked_pngs(self):
        text = (SITE / 'seed_data.py').read_text(encoding='utf-8')
        self.assertIn('/static/icons/airlines/{airline_code}.png', text)
        self.assertNotIn('/static/images/airlines/{airline_slug}.svg', text)
        self.assertNotIn('/static/images/airlines/{airline_slug}.png', text)

    def test_templates_resolve_logos_without_onerror_hide(self):
        for path in TEMPLATES:
            text = path.read_text(encoding='utf-8')
            self.assertIn('airline_logo_url(', text, path.name)
            self.assertNotIn("src=\"{{ f.airline_logo }}\"", text, path.name)
            self.assertNotIn("onerror=\"this.style.display='none'\"", text, path.name)


class AirlineLogoResolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SITE))
        import app as gf
        cls.gf = gf

    def test_prefers_committed_png_over_letter_tile_svg(self):
        flight = SimpleNamespace(
            airline='Delta',
            airline_code='DL',
            airline_logo='/static/images/airlines/delta.svg',
        )
        rel = self.gf.airline_logo_relpath(flight)
        self.assertEqual(rel, 'icons/airlines/DL.png')
        with self.gf.app.test_request_context('/'):
            url = self.gf.airline_logo_url(flight)
        self.assertEqual(url, '/static/icons/airlines/DL.png')

    def test_recovers_code_from_seed_slug_when_code_missing(self):
        flight = SimpleNamespace(
            airline='Delta',
            airline_code='',
            airline_logo='/static/images/airlines/delta.svg',
        )
        self.assertEqual(self.gf.airline_logo_relpath(flight), 'icons/airlines/DL.png')

    def test_unknown_airline_falls_back_to_existing_db_path(self):
        flight = SimpleNamespace(
            airline='Mystery Air',
            airline_code='ZZ',
            airline_logo='/static/images/airlines/delta.svg',
        )
        # No ZZ.png; letter-tile SVG from the published bundle still exists.
        self.assertEqual(
            self.gf.airline_logo_relpath(flight),
            'images/airlines/delta.svg',
        )


class AirlineLogoHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed = SITE / 'instance_seed' / 'google_flights.db'
        if not seed.is_file():
            raise unittest.SkipTest('google_flights seed DB is not present')
        sys.path.insert(0, str(SITE))
        import app as gf
        gf.app.config['TESTING'] = True
        cls.gf = gf
        cls.client = gf.app.test_client()
        cls.codes = {code for _name, code, _slug in _airlines()}
        con = sqlite3.connect(SITE / 'instance' / 'google_flights.db')
        row = con.execute(
            'SELECT f.id, a.iata, b.iata, f.departure_date, f.airline_code '
            'FROM flight f '
            'JOIN airport a ON a.id = f.origin_id '
            'JOIN airport b ON b.id = f.destination_id '
            'LIMIT 1'
        ).fetchone()
        con.close()
        cls.sample = row

    def test_static_pngs_are_served(self):
        for code in sorted(self.codes):
            resp = self.client.get(f'/static/icons/airlines/{code}.png')
            try:
                self.assertEqual(resp.status_code, 200, code)
                self.assertIn('image/png', resp.content_type)
                self.assertTrue(resp.data.startswith(PNG_SIG), code)
            finally:
                resp.close()

    def test_flights_and_search_emit_icon_pngs_not_missing_svgs(self):
        flight_id, origin, dest, depart, code = self.sample
        flights = self.client.get(
            f'/flights?from={origin}&to={dest}&depart={depart}'
        )
        self.assertEqual(flights.status_code, 200)
        body = flights.get_data(as_text=True)
        self.assertIn('/static/icons/airlines/', body)
        self.assertNotIn('/static/images/airlines/', body)
        self.assertNotIn("onerror=\"this.style.display='none'\"", body)
        served = set(re.findall(r'/static/icons/airlines/([A-Z0-9]{2,3})\.png', body))
        self.assertTrue(served, 'no airline icon URLs on /flights')
        self.assertTrue(served <= self.codes)

        search = self.client.get('/search?q=Delta')
        self.assertEqual(search.status_code, 200)
        sbody = search.get_data(as_text=True)
        self.assertIn('/static/icons/airlines/DL.png', sbody)
        self.assertNotIn('/static/images/airlines/delta.svg', sbody)

        detail = self.client.get(f'/flight/{flight_id}')
        self.assertEqual(detail.status_code, 200)
        dbody = detail.get_data(as_text=True)
        # Related-flight cards on the detail page must use real logos.
        self.assertNotIn('/static/images/airlines/', dbody)


if __name__ == '__main__':
    unittest.main()
