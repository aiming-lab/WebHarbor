from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _support import SEED_DB, State, USERS, step, write_run  # noqa: E402
import verify_lib as lib  # noqa: E402


class MatcherTests(unittest.TestCase):
    def test_contains_count_standalone_only(self) -> None:
        self.assertTrue(lib.contains_count("kilometer 38", 38))
        self.assertTrue(lib.contains_count("thirty-eight? no: 38.", 38))
        self.assertFalse(lib.contains_count("kilometer 380", 38))
        self.assertFalse(lib.contains_count("3.8 km", 38))
        self.assertFalse(lib.contains_count("38th kilometre", 38))
        self.assertTrue(lib.contains_count("three attempts", 3))
        self.assertFalse(lib.contains_count("3.5 attempts", 3))
        self.assertFalse(lib.contains_count("13 attempts", 3))
        self.assertTrue(lib.contains_count("eleven days", 11))

    def test_contains_decimal(self) -> None:
        self.assertTrue(lib.contains_decimal("4.2 meters", "4.2"))
        self.assertTrue(lib.contains_decimal("4,2 m", "4.2"))
        self.assertFalse(lib.contains_decimal("4.25 meters", "4.2"))
        self.assertFalse(lib.contains_decimal("14.2 meters", "4.2"))

    def test_contains_clock_time(self) -> None:
        for text in ("6 a.m.", "6am", "6:00 AM", "06:00", "at 6 A.M. sharp"):
            self.assertTrue(lib.contains_clock_time(text, "6 am"), text)
        for text in ("6 p.m.", "18:00", "16:00", "6:30 am"):
            self.assertFalse(lib.contains_clock_time(text, "6 am"), text)

    def test_contains_phrase_join_variants(self) -> None:
        for text in ("a lunch box", "a lunchbox", "a lunch-box", "LUNCH BOX"):
            self.assertTrue(lib.contains_phrase(text, "lunch box"), text)
        self.assertFalse(lib.contains_phrase("a lunch bag and a box", "lunch box"))

    def test_negation_is_not_affirmative(self) -> None:
        self.assertFalse(lib.contains_all("the flags were not orange", ("orange",)))
        self.assertFalse(lib.contains_all("orange is wrong; they were red", ("orange",)))
        self.assertTrue(lib.contains_all("not red, orange", ("orange",)))
        self.assertTrue(lib.contains_all("The flags were orange, not red.", ("orange",)))

    def test_search_visited_uses_whole_tokens(self) -> None:
        traj = {"start_url": "http://localhost:41024/", "steps": [step("/search?q=lighthouses+near+me")]}
        self.assertTrue(lib.search_visited(traj, ("lighthouses",)))
        self.assertFalse(lib.search_visited(traj, ("lighthouse",)))
        self.assertFalse(lib.search_visited({"steps": [step("/tag/lighthouse")]}, ("lighthouse",)))

    def test_detail_visited_is_exact_path(self) -> None:
        traj = {"steps": [step("/gag/some-post-1/report")]}
        self.assertFalse(lib.detail_visited(traj, "some-post-1"))
        traj = {"steps": [step("/gag/some-post-1/")]}
        self.assertTrue(lib.detail_visited(traj, "some-post-1"))

    def test_paths_in_order(self) -> None:
        traj = {"steps": [step("/login"), step("/home"), step("/settings")]}
        self.assertTrue(lib.paths_in_order(traj, [("/login", {}), ("/settings", {})]))
        self.assertFalse(lib.paths_in_order(traj, [("/settings", {}), ("/login", {})]))

    def test_site_url_accepts_loopback_only(self) -> None:
        self.assertTrue(lib.is_site_url("http://localhost:40026/"))
        self.assertTrue(lib.is_site_url("http://127.0.0.1:45001/x"))
        self.assertFalse(lib.is_site_url("https://9gag.com/"))
        self.assertFalse(lib.is_site_url("file:///tmp/x"))


class SeedContractTests(unittest.TestCase):
    def test_frozen_seed_matches_pinned_contract(self) -> None:
        self.assertEqual(lib.schema_sha256(SEED_DB), lib.SCHEMA_SHA256)
        counts = {t: len(lib.table_rows(SEED_DB, t)) for t in lib.SEED_COUNTS}
        self.assertEqual(counts, lib.SEED_COUNTS)
        lib.validate_snapshot_contract(str(SEED_DB), str(SEED_DB))

    def test_password_matches_real_werkzeug_hash(self) -> None:
        for _, email, _ in USERS.values():
            row = lib.user_row(SEED_DB, email)
            self.assertTrue(lib.password_matches(row["password_hash"], "TestPass123!"), email)
            self.assertFalse(lib.password_matches(row["password_hash"], "testpass123!"), email)
        self.assertFalse(lib.password_matches("garbage", "x"))

    def test_synthetic_user_hash_round_trips(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            db = State().add_user("x@test.com", "x_user", "Secret123!").write(Path(d) / "a.db")
            self.assertTrue(lib.password_matches(lib.user_row(db, "x@test.com")["password_hash"], "Secret123!"))

    def test_table_delta_reports_exact_rows(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            initial = State().write(Path(d) / "i.db")
            after = State().add_saved(1, 12).write(Path(d) / "a.db")
            delta = lib.table_delta(initial, after, "saved_post")
            self.assertEqual(len(delta["added"]), 1)
            self.assertEqual(tuple(delta["added"][0][1:]), (1, 12))
            self.assertEqual(lib.changed_tables(initial, after), ["saved_post"])


class PackageTests(unittest.TestCase):
    def test_screenshots_decode_requires_every_referenced_png(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "run"
            write_run(run, "9GAG--0", [step("/"), step("/x", "done")], "answer")
            traj = lib.load_run(run)
            self.assertTrue(lib.screenshots_decode(traj)[0])
            (run / "screenshots" / "step_001.png").unlink()
            self.assertFalse(lib.screenshots_decode(lib.load_run(run))[0])

    def test_no_llm_flag_disables_helpers(self) -> None:
        lib.Judge("9GAG--0", no_llm=True)
        self.assertEqual(lib.llm_text_match("a", "b", "q"), (False, "[skipped: --no_llm]"))
        judge = lib.Judge("9GAG--0", no_llm=False)
        lib.advisory_llm_answer(judge, "a", "b", "q")  # no env configured -> no call, no evidence
        self.assertEqual(judge.evidence, [])


if __name__ == "__main__":
    unittest.main()
