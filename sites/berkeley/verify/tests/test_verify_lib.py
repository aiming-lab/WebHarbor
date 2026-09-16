"""Unit tests for the shared helpers, the snapshot contract and the source-fact rules.

No docker, no LLM: matcher behaviour, gate semantics, the fingerprint recipe and
the three assertions that keep the About/Admissions values source-sourced.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402
    BASE, SITE_DIR, SEED_DB, State, seed_fingerprint, step, write_run,
)

VERIFY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY_DIR))

import ground_truth  # noqa: E402
import verify_lib as lib  # noqa: E402


class SnapshotContractTests(unittest.TestCase):
    def test_seed_fingerprint_matches_the_pinned_contract(self) -> None:
        self.assertEqual(lib.catalog_fingerprint(str(SEED_DB)), lib.CATALOG_FINGERPRINT)
        self.assertEqual(seed_fingerprint(), lib.CATALOG_FINGERPRINT)

    def test_seed_counts_and_schema_hash_match(self) -> None:
        observed = {table: len(lib.table_rows(str(SEED_DB), table)) for table in lib.EXPECTED_COUNTS}
        self.assertEqual(observed, lib.EXPECTED_COUNTS)
        schema_hash = lib.hashlib.sha256(
            json.dumps(lib._schema_objects(str(SEED_DB)), separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(schema_hash, lib.SCHEMA_HASH)

    def test_stdlib_fixture_pipeline_reproduces_the_fingerprint(self) -> None:
        """A copy of the seed rewritten through the stdlib fixture keeps the catalog intact."""
        with tempfile.TemporaryDirectory() as tmp:
            path = State().write(Path(tmp) / "fixture.db")
            self.assertEqual(lib.catalog_fingerprint(str(path)), lib.CATALOG_FINGERPRINT)

    def test_state_rewrite_changes_only_the_bookmarks_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            after = Path(tmp) / "after.db"
            state = State()
            state.add_bookmark(1, "research", 8)
            state.write(after)
            changed = [table for table in lib.ALL_TABLES
                       if lib.table_rows(str(SEED_DB), table) != lib.table_rows(str(after), table)]
            self.assertEqual(changed, ["bookmarks"])

    def test_contract_rejects_catalog_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial = State().write_with_catalog_change(Path(tmp) / "initial.db")
            after = State().write(Path(tmp) / "after.db")
            with self.assertRaises(ValueError):
                lib._validate_snapshot_contract(str(initial), str(after))

    def test_contract_rejects_a_catalog_mutation_in_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial = State().write(Path(tmp) / "initial.db")
            after = State().write_with_catalog_change(Path(tmp) / "after.db")
            with self.assertRaises(ValueError):
                lib._validate_snapshot_contract(str(initial), str(after))

    def test_contract_accepts_a_bookmark_only_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial = State().write(Path(tmp) / "initial.db")
            state = State()
            state.add_bookmark(1, "research", 8)
            after = state.write(Path(tmp) / "after.db")
            lib._validate_snapshot_contract(str(initial), str(after))  # must not raise


class GroundTruthTests(unittest.TestCase):
    def test_every_kept_task_derives(self) -> None:
        facts = ground_truth.all_ground_truth(str(SEED_DB))
        self.assertEqual(
            sorted(facts),
            [1, 2, 4, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 27, 28, 30, 31],
        )

    def test_unsupported_task_fails(self) -> None:
        with self.assertRaises(ValueError):
            ground_truth.task_ground_truth(str(SEED_DB), 3)

    def test_dropped_and_unrelated_ids_fail_closed(self) -> None:
        for dropped in (0, 3, 5, 8, 9, 15, 18, 21, 26, 29, 32):
            with self.assertRaises(ValueError):
                ground_truth.task_ground_truth(str(SEED_DB), dropped)

    def test_event_targets_respect_the_frozen_clock(self) -> None:
        lecture = ground_truth.task_ground_truth(str(SEED_DB), 6)
        worker = sqlite3.connect(str(SEED_DB))
        try:
            total = worker.execute("SELECT COUNT(*) FROM events WHERE category='Lecture'").fetchone()[0]
        finally:
            worker.close()
        self.assertLess(len(lecture["upcoming"]), total)
        self.assertTrue(all(row["start_datetime"] >= ground_truth.BENCHMARK_NOW for row in lecture["upcoming"]))

    def test_task_27_reanchored_targets(self) -> None:
        facts = ground_truth.task_ground_truth(str(SEED_DB), 27)
        self.assertEqual(facts["durations"], (1.0, 1.5))
        self.assertEqual(facts["meng"]["department_name"], facts["ms"]["department_name"])

    def test_stateful_targets_bind_to_empty_bookmark_table(self) -> None:
        facts = ground_truth.task_ground_truth(str(SEED_DB), 31)
        self.assertLess(facts["first"]["id"], facts["second"]["id"])
        self.assertEqual(len(lib.table_rows(str(SEED_DB), "bookmarks")), 0)


class SourceFactsTests(unittest.TestCase):
    """Decision 6: the About/Admissions values are tracked source, not DB rows."""

    def test_admissions_facts_come_from_the_template(self) -> None:
        facts = ground_truth.admissions_facts()
        template = (SITE_DIR / "templates" / "admissions.html").read_text(encoding="utf-8")
        self.assertIn(facts["deadline"], template)
        self.assertIn(facts["acceptance_rate"], template)
        self.assertRegex(facts["deadline"], r"^[A-Z][a-z]+ \d{1,2}$")
        self.assertRegex(facts["acceptance_rate"], r"^\d+(?:\.\d+)?%$")

    def test_about_stats_are_source_literals_not_db(self) -> None:
        facts = ground_truth.about_facts()
        self.assertEqual(set(facts), {"nobel_laureates", "varsity_sports", "national_titles"})
        source = (SITE_DIR / "app.py").read_text(encoding="utf-8")
        template = (SITE_DIR / "templates" / "about.html").read_text(encoding="utf-8")
        worker = sqlite3.connect(str(SEED_DB))
        try:
            columns = {
                column[1]
                for table in lib.EXPECTED_TABLES
                for column in worker.execute(f"PRAGMA table_info({table})")
            }
        finally:
            worker.close()
        for key, value in facts.items():
            self.assertRegex(source, rf"'{key}':\s*{value}\b")
            self.assertIn(f"stats.{key}", template)
            self.assertNotIn(key, columns)
        self.assertGreater(ground_truth.about_distractor_prizes(), max(facts.values()))

    def test_verifier_package_never_imports_an_llm(self) -> None:
        for path in sorted(VERIFY_DIR.glob("verify_*.py")):
            text = path.read_text(encoding="utf-8")
            for banned in ("openai", "llm_text_match", "llm_screenshot_shows"):
                self.assertNotIn(banned, text, f"{path.name} references {banned}")


class MatcherTests(unittest.TestCase):
    def test_contains_count_forms_and_guards(self) -> None:
        self.assertTrue(lib.contains_count("There are 17 programs.", 17))
        self.assertTrue(lib.contains_count("seventeen programs", 17))
        self.assertTrue(lib.contains_count("4,500 undergraduates", 4500))
        self.assertTrue(lib.contains_count("4500 undergraduates", 4500))
        self.assertTrue(lib.contains_count("count: 8", 8))
        self.assertTrue(lib.contains_count("eight departments", 8))
        self.assertFalse(lib.contains_count("25 programs", 17))
        self.assertFalse(lib.contains_count("12,000 students", 12))
        self.assertFalse(lib.contains_count("14.4%", 14))
        self.assertFalse(lib.contains_count("built in 2013", 1))
        self.assertFalse(lib.contains_count("18 departments", 8))

    def test_contains_percent(self) -> None:
        self.assertTrue(lib.contains_percent("14.4%", "14.4%"))
        self.assertTrue(lib.contains_percent("14.4 percent", "14.4%"))
        self.assertTrue(lib.contains_percent("rate: 14.4 per cent", "14.4%"))
        self.assertFalse(lib.contains_percent("11%", "14.4%"))
        self.assertFalse(lib.contains_percent("14.4", "14.4%"))

    def test_contains_date_variants(self) -> None:
        value = _dt.date(2026, 5, 15)
        for text in ("May 15, 2026", "May 15 2026", "15 May 2026", "2026-05-15", "05/15/2026", "May 15"):
            self.assertTrue(lib.contains_date(text, value), text)
        self.assertFalse(lib.contains_date("May 16, 2026", value))
        self.assertFalse(lib.contains_date("May 2015", value))

    def test_contains_month_day(self) -> None:
        self.assertTrue(lib.contains_month_day("due by November 30", "November 30"))
        self.assertTrue(lib.contains_month_day("due by Nov. 30, 2026", "November 30"))
        self.assertFalse(lib.contains_month_day("due by December 1", "November 30"))
        self.assertFalse(lib.contains_month_day("due by November 3", "November 30"))

    def test_contains_person_ignores_titles(self) -> None:
        self.assertTrue(lib.contains_person("Prof. James Demmel is the chair.", "Prof. James Demmel"))
        self.assertTrue(lib.contains_person("the dean is Tsu-Jae King Liu", "Dean Tsu-Jae King Liu"))
        self.assertFalse(lib.contains_person("Demmel", "Prof. James Demmel"))
        self.assertFalse(lib.contains_person("James", "Prof. James Demmel"))

    def test_contains_location_room_number_optional(self) -> None:
        self.assertTrue(lib.contains_location("located at 253 Cory Hall", "253 Cory Hall"))
        self.assertTrue(lib.contains_location("located at Cory Hall", "253 Cory Hall"))
        self.assertFalse(lib.contains_location("located at Soda Hall", "253 Cory Hall"))

    def test_contains_degree_type_variants(self) -> None:
        self.assertTrue(lib.contains_degree_type("offers a Ph.D.", "PhD"))
        self.assertTrue(lib.contains_degree_type("the MEng programme", "MEng"))
        self.assertTrue(lib.contains_degree_type("a BS in CS", "BS"))
        self.assertFalse(lib.contains_degree_type("the master's programme", "MS"))
        self.assertFalse(lib.contains_degree_type("business administration", "BA"))

    def test_contains_duration_years_distinguishes_one_and_one_and_a_half(self) -> None:
        self.assertTrue(lib.contains_duration_years("takes 1 year", 1.0))
        self.assertTrue(lib.contains_duration_years("lasts one year", 1.0))
        self.assertTrue(lib.contains_duration_years("runs 1.5 years", 1.5))
        self.assertTrue(lib.contains_duration_years("about 18 months", 1.5))
        self.assertFalse(lib.contains_duration_years("takes 1.5 years", 1.0))
        self.assertFalse(lib.contains_duration_years("takes 2 years", 1.0))
        self.assertFalse(lib.contains_duration_years("takes 1 year", 1.5))

    def test_contains_year_allows_sentence_final_stop(self) -> None:
        self.assertTrue(lib.contains_year("established in 2013.", 2013))
        self.assertTrue(lib.contains_year("founded 2013, not 2017", 2013))
        self.assertFalse(lib.contains_year("founded in 2017.", 2013))

    def test_negation_semantics(self) -> None:
        self.assertFalse(lib.contains_phrase("did not receive the National Medal of Science", "National Medal of Science"))
        self.assertFalse(lib.contains_phrase("the award was not the National Medal of Science", "National Medal of Science"))
        self.assertFalse(lib.contains_count("does not have 12 departments", 12))
        self.assertFalse(lib.contains_phrase("no Lecture events", "Lecture"))
        # A confirming contrast stays affirmative.
        self.assertTrue(lib.contains_year("founded in 2013, not 2017", 2013))
        self.assertTrue(lib.contains_count("1 year, not 2 years", 1))
        # Negation after the value still rejects it.
        self.assertFalse(lib.contains_year("2013 was not the founding year", 2013))
        # An honorific's period must not split the clause and hide a negation
        # (C2 mutation rows on tasks 13/23/24).
        self.assertFalse(lib.contains_person(
            "The chair of EECS is not Prof. James Demmel, and the department is located at 253 Cory Hall.",
            "Prof. James Demmel",
        ))
        self.assertTrue(lib.contains_person(
            "The chair of EECS is Prof. James Demmel, located at 253 Cory Hall.", "Prof. James Demmel"))
        self.assertFalse(lib.contains_phrase(
            "BIDS is not directed by Prof. David Culler.", "The Berkeley Institute"))
        self.assertFalse(lib.contains_phrase("holds a Ph.D. It is not the largest college.", "largest college"))

    def test_contains_count_as_pins_the_label(self) -> None:
        self.assertTrue(lib.contains_count_as("107 Nobel Laureates on the faculty", 107, "laureates"))
        self.assertFalse(lib.contains_count_as("more than 107 Nobel Prizes in total", 107, "laureates"))

    def test_title_tokens_and_matching(self) -> None:
        title = "Women's Gymnastics Wins NCAA Championship"
        self.assertGreaterEqual(lib.title_tokens_matched("women's gymnastics won the NCAA championship", title), 3)
        self.assertLess(lib.title_tokens_matched("won a championship", title), 3)

    def test_department_aliases_and_acronyms(self) -> None:
        name = "Department of Electrical Engineering and Computer Sciences"
        self.assertTrue(lib.contains_department("offered by EECS", name))
        self.assertTrue(lib.contains_department("the Electrical Engineering and Computer Sciences department", name))
        self.assertFalse(lib.contains_department("offered by the Math department", name))
        self.assertEqual(lib.acronym("Mathematical Sciences Research Institute"), "msri")
        self.assertEqual(lib.acronym("Economics"), "")

    def test_interest_token_matches_counts_distinct_tokens(self) -> None:
        interests = "Artificial intelligence, machine learning, AI safety, probabilistic reasoning"
        self.assertGreaterEqual(lib.interest_token_matches("works on machine learning and AI safety", interests), 2)
        self.assertLess(lib.interest_token_matches("works on robotics", interests), 2)

    def test_affirmative_near(self) -> None:
        self.assertTrue(
            lib.affirmative_near("the Spring Career Fair: registration is required", "career fair", "required", 80)
        )
        self.assertFalse(
            lib.affirmative_near("the Spring Career Fair is not open; registration not required", "career fair", "required", 80)
        )


class UrlGateTests(unittest.TestCase):
    def trajectory(self, steps):
        return {"start_url": f"{BASE}/", "steps": steps}

    def test_params_visited_matches_first_value_only(self) -> None:
        traj = self.trajectory([step("/programs?degree=PhD&degree=MS")])
        self.assertTrue(lib.params_visited(traj, "/programs", degree="PhD"))
        self.assertFalse(lib.params_visited(traj, "/programs", degree="MS"))

    def test_params_visited_alternatives_and_regex(self) -> None:
        traj = self.trajectory([step("/news?q=CRISPR")])
        self.assertTrue(lib.params_visited(traj, "/news", q="crispr"))
        self.assertTrue(lib.params_visited(traj, "/news", q=lib.re.compile(r"crisp")))
        self.assertFalse(lib.params_visited(traj, "/news", category="Research"))

    def test_detail_gates_are_exact(self) -> None:
        traj = self.trajectory([step("/programs/computer-science-bs-extra")])
        self.assertFalse(lib.detail_visited(traj, "program", "computer-science-bs"))
        traj = self.trajectory([step("/programs/computer-science-bs")])
        self.assertTrue(lib.detail_visited(traj, "program", "computer-science-bs"))
        self.assertEqual(lib.detail_path("event", 2), "/events/2")

    def test_last_action_target_counts_as_a_visit(self) -> None:
        traj = self.trajectory([step("/"), {"url": f"{BASE}/", "action": "navigate",
                                            "params": {"url": f"{BASE}/about"}}])
        self.assertTrue(lib.navigated_to_path(traj, "/about"))

    def test_paths_in_order(self) -> None:
        traj = self.trajectory([step("/departments"), step("/departments/eecs")])
        lib.check_paths_in_order(lib.Judge("t"), traj, "order", [("/departments", {}), ("/departments/eecs", {})])
        bad = self.trajectory([step("/departments/eecs"), step("/departments")])
        judge = lib.Judge("t")
        self.assertFalse(lib.check_paths_in_order(judge, bad, "order", [("/departments", {}), ("/departments/eecs", {})]))

    def test_listing_pages_are_distinct(self) -> None:
        traj = self.trajectory([step("/programs?page=1"), step("/programs?page=1"), step("/programs?page=2")])
        self.assertEqual(len(lib.listing_pages_visited(traj, "/programs")), 2)

    def test_origin_rules(self) -> None:
        self.assertTrue(lib.is_site_url("http://localhost:41026/x"))
        self.assertTrue(lib.is_site_url("http://127.0.0.1:41026/x"))
        self.assertFalse(lib.is_site_url("http://example.com/x"))
        self.assertFalse(lib._same_local_origin("http://localhost:9999/x", f"{BASE}/"))

    def test_screenshot_size_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            write_run(run_dir, "UC Berkeley--1", [step("/")], "answer")
            judge = lib.Judge("t")
            trajectory = lib.load_run(run_dir)
            lib.check_trajectory_identity(judge, trajectory, "UC Berkeley--1")
            self.assertTrue(judge.passed)


class BookmarkHelperTests(unittest.TestCase):
    def test_delta_and_row_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial = State().write(Path(tmp) / "initial.db")
            state = State()
            state.add_bookmark(2, "research", 9)   # id 1
            state.add_bookmark(2, "research", 22)  # id 2
            state.remove_bookmark(1)
            after = state.write(Path(tmp) / "after.db")
            delta = lib.bookmark_delta(str(initial), str(after), 2)
            self.assertEqual([lib.bookmark_identity(row) for row in delta["added"]], [(2, "research", 22)])
            self.assertEqual(delta["removed"], [])
            judge = lib.Judge("t")
            lib.check_bookmarks_delta(judge, str(initial), str(after), user_id=2,
                                      added=[(2, "research", 22)], surviving_ids=[2])
            self.assertTrue(judge.passed, judge.evidence)

    def test_surviving_id_pin_rejects_the_reversed_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            initial = State().write(Path(tmp) / "initial.db")
            state = State()
            state.add_bookmark(2, "research", 22)  # id 1: the wrong order
            state.add_bookmark(2, "research", 9)   # id 2
            state.remove_bookmark(2)
            after = state.write(Path(tmp) / "after.db")
            judge = lib.Judge("t")
            lib.check_bookmarks_delta(judge, str(initial), str(after), user_id=2,
                                      added=[(2, "research", 22)], surviving_ids=[2])
            self.assertFalse(judge.passed)
            self.assertEqual(judge.reason, "bookmarks_surviving_row_ids")


if __name__ == "__main__":
    unittest.main()
