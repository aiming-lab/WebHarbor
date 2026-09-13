from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_lib as L  # noqa: E402
from _support import SITE_DIR, State, build_seed, scrypt_hash  # noqa: E402


class FixtureMatchesFrozenSeed(unittest.TestCase):
    def test_fixture_catalog_fingerprint_equals_pinned_constant(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = build_seed(Path(d) / "seed.db")
            self.assertEqual(L.catalog_fingerprint(db), L.CATALOG_FINGERPRINT)
            L._validate_snapshot_contract(str(db), str(db))

    def test_real_seed_if_present_matches_fixture(self) -> None:
        real = SITE_DIR / "instance_seed" / "accuweather.db"
        if not real.is_file():
            self.skipTest("instance_seed/accuweather.db not generated in this checkout")
        self.assertEqual(L.catalog_fingerprint(real), L.CATALOG_FINGERPRINT)


class FactMatchers(unittest.TestCase):
    def test_contains_fact_unit_and_label(self) -> None:
        self.assertTrue(L.contains_fact("temperature 104°F", 104, unit="temp", label=L.TEMP_LABEL))
        self.assertTrue(L.contains_fact("104° and RealFeel 115°", 104, unit="temp", label=L.TEMP_LABEL))
        self.assertTrue(L.contains_fact("RealFeel® temperature of 115°", 115, unit="temp", label=L.REALFEEL_LABEL))
        self.assertTrue(L.contains_fact("RealFeel® temperature of 115°", 104, unit="temp", label=L.TEMP_LABEL) is False)
        self.assertFalse(L.contains_fact("temperature 115, RealFeel 104", 104, unit="temp", label=L.TEMP_LABEL))
        self.assertTrue(L.contains_fact("18% humidity, RealFeel 115", 18, unit="percent", label=L.HUMIDITY_LABEL, allow_bare=False))
        self.assertFalse(L.contains_fact("humidity 181%", 18, unit="percent", label=L.HUMIDITY_LABEL, allow_bare=False))
        self.assertFalse(L.contains_fact("humidity is not 18%", 18, unit="percent", label=L.HUMIDITY_LABEL))
        self.assertTrue(L.contains_fact("pressure 29.89 in", "29.89", unit="inhg", label=L.PRESSURE_LABEL))
        self.assertFalse(L.contains_fact("pressure 29.8 in", "29.89", unit="inhg", label=L.PRESSURE_LABEL))
        self.assertTrue(L.contains_fact("Austin's RealFeel is 103°", 103, unit="temp", label=L.city_label("austin")))
        self.assertFalse(L.contains_fact("Austin 82°, Denver 103°", 103, unit="temp", label=L.city_label("austin")))

    def test_conditions_days_and_times(self) -> None:
        self.assertTrue(L.contains_condition("it is mostly cloudy", "Mostly cloudy"))
        self.assertFalse(L.contains_condition("Mostly cloudy", "Cloudy"))
        self.assertTrue(L.contains_condition("Cloudy skies", "Cloudy"))
        self.assertFalse(L.contains_condition("partly sunny", "Sunny"))
        self.assertTrue(L.contains_day_label("Saturday", "Sat") and L.contains_day_label("Sat.", "Sat"))
        self.assertFalse(L.contains_day_label("Sunday", "Sat"))
        self.assertTrue(L.contains_clock_time("at 16:00", "4 PM") and L.contains_clock_time("4:00 p.m.", "4 PM"))
        self.assertFalse(L.contains_clock_time("4 AM", "4 PM"))

    def test_names_winner(self) -> None:
        w, l = ["denver"], ["austin"]
        kw, inv = ["cooler", "lower"], ["warmer", "hotter"]
        for good in ["Denver feels cooler than Austin", "Austin 103, Denver 82; Denver feels cooler",
                     "The cooler city is Denver", "Denver (82°) is cooler", "Austin is warmer than Denver",
                     "Austin 103 and Denver 82, so Denver feels cooler", "cooler: Denver"]:
            self.assertTrue(L.names_winner(good, w, l, kw, inv), good)
        for bad in ["Austin feels cooler than Denver", "The cooler city is Austin", "Denver is warmer",
                    "Austin 103, Denver 82", "Denver feels cooler. Austin feels cooler too."]:
            self.assertFalse(L.names_winner(bad, w, l, kw, inv), bad)

    def test_search_surfaces_and_origin(self) -> None:
        traj = {"start_url": "http://localhost:41024/", "steps": [{"url": "http://localhost:41024/search?q=Springfield+Missouri"}]}
        self.assertTrue(L.search_surfaces(traj, "springfield-mo"))
        self.assertTrue(L.search_surfaces(traj, "springfield-il"))
        self.assertFalse(L.search_surfaces(traj, "phoenix-az"))

    def test_search_gate_ignores_catalog_wide_tokens(self) -> None:
        """``United States`` matches 20/20 locations, so it must not satisfy the
        anti-shortcut gate for any of them; a city/region/postal token must."""
        def q(term):
            return {"start_url": "http://localhost:41024/",
                    "steps": [{"url": "http://localhost:41024/search?q=" + term}]}
        for slug in ("springfield-mo", "portland-me", "toronto-ca", "london-gb"):
            self.assertFalse(L.search_surfaces(q("United+States"), slug), slug)
            self.assertFalse(L.search_surfaces(q("states"), slug), slug)
        self.assertTrue(L.search_surfaces(q("Springfield"), "springfield-mo"))
        self.assertTrue(L.search_surfaces(q("65806"), "springfield-mo"))
        self.assertTrue(L.search_surfaces(q("Kingdom"), "london-gb"))
        self.assertNotIn("united", L._discriminative_tokens("london-gb"))
        self.assertIn("london", L._discriminative_tokens("london-gb"))

    def test_screenshots_reject_stub_sizes(self) -> None:
        """A decodable but 1x1 PNG is a placeholder, not page evidence."""
        from _support import make_png
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "screenshots").mkdir()
            traj = {"_run_dir": root, "steps": [{"screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}]}
            for w, h, expected in ((320, 200, True), (L.MIN_SHOT_WIDTH, L.MIN_SHOT_HEIGHT, True),
                                   (1, 1, False), (L.MIN_SHOT_WIDTH - 1, L.MIN_SHOT_HEIGHT, False),
                                   (L.MIN_SHOT_WIDTH, L.MIN_SHOT_HEIGHT - 1, False)):
                for name in ("step_000.png", "step_001.png"):
                    (root / "screenshots" / name).write_bytes(make_png(w, h))
                ok, evidence = L.screenshots_decode(traj)
                self.assertEqual(ok, expected, f"{w}x{h}: {evidence}")
        self.assertTrue(L.navigated_to_path({"steps": [{"url": "http://127.0.0.1:5000/weather/phoenix-az?x=1"}]}, "/weather/phoenix-az"))
        self.assertFalse(L.navigated_to_path({"steps": [{"url": "http://example.com/weather/phoenix-az"}]}, "/weather/phoenix-az"))
        self.assertFalse(L._same_local_origin("http://localhost:41025/", "http://localhost:41024/"))

    def test_password_matches(self) -> None:
        self.assertTrue(L.password_matches(scrypt_hash("Weather123!"), "Weather123!"))
        self.assertFalse(L.password_matches(scrypt_hash("Weather123!"), "weather123!"))
        self.assertFalse(L.password_matches("garbage", "x"))


if __name__ == "__main__":
    unittest.main()
