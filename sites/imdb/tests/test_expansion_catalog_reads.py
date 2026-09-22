"""Constructed offline cases only; none of these are genuine UI runs."""

import importlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE / "verify"))
grader = importlib.import_module("expansion_catalog_reads")
RunEvidence = importlib.import_module("verify_lib").RunEvidence
VerificationError = importlib.import_module("verify_lib").VerificationError

SCHEMA = """
CREATE TABLE titles (id INTEGER PRIMARY KEY, tt_id TEXT, title_type TEXT,
 primary_title TEXT, original_title TEXT DEFAULT '', year INTEGER,
 runtime_min INTEGER, mpaa_rating TEXT, rating_avg REAL, budget INTEGER,
 box_office_opening INTEGER, box_office_us INTEGER, box_office_world INTEGER,
 release_date TEXT);
CREATE TABLE persons (id INTEGER PRIMARY KEY, nm_id TEXT, name TEXT);
CREATE TABLE credits (id INTEGER PRIMARY KEY, title_id INTEGER, person_id INTEGER,
 role TEXT, billing_order INTEGER);
CREATE TABLE genres (id INTEGER PRIMARY KEY, slug TEXT);
CREATE TABLE title_genre (title_id INTEGER, genre_id INTEGER);
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE reviews (id INTEGER PRIMARY KEY, body TEXT);
CREATE TABLE user_ratings (id INTEGER PRIMARY KEY, rating INTEGER);
CREATE TABLE watchlist_items (id INTEGER PRIMARY KEY, title_id INTEGER);
"""

ANSWERS = {
    18: ("| Film | IMDb rating | Runtime | MPAA |\n|---|---|---|---|\n"
         "| Amber Run | 8.5 | 90 minutes | G |\n"
         "| Bronze Tide | 8.5 | 100 minutes | PG |\n"
         "| Cedar Light | 8.5 | 95 minutes | G |\n\n"
         "Best pair: Amber Run + Bronze Tide; combined runtime 190 minutes; summed rating 17.0.\n"
         "Best pair: Cedar Light + Amber Run; combined runtime 185 minutes; summed rating 17.0."),
    19: ("| Film | Budget | Opening weekend US & Canada | Percentage |\n|---|---|---|---|\n"
         "| Amber Run | $70.0M | $30.6M | 43.7% |\n"
         "| Bronze Tide | $52.0M | $30.1M | 57.9% |\n\nWinner: Bronze Tide (57.9%)."),
    20: ("| Film | Gross US & Canada | Gross worldwide | Remainder share |\n|---|---|---|---|\n"
         "| Amber Run | $30.0M | $100.0M | 70.0% |\n"
         "| Bronze Tide | $120.0M | $200.0M | 40.0% |\n"
         "| Cedar Light | $150.0M | $300.0M | 50.0% |\n\nWinner: Amber Run (70.0%)."),
    23: ("| Film | Release date |\n|---|---|\n"
         "| Amber Run | 2000-01-01 |\n| Bronze Tide | 2000-01-05 |\n"
         "| Cedar Light | 2000-01-09 |\n\n"
         "Closest pair: Amber Run to Bronze Tide — 4 calendar days.\n"
         "Closest pair: Bronze Tide to Cedar Light — 4 days."),
}


class CatalogReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.origin = "http://catalog-read.localhost:48021"
        with sqlite3.connect(self.folder / "before.db") as db:
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO titles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (1, "tt9000001", "movie", "Amber Run", "", 2000, 90, "G", 8.5,
                 70000000, 30576104, 29960000, 100040000, "2000-01-01"),
                (2, "tt9000002", "movie", "Bronze Tide", "", 2000, 100, "PG", 8.5,
                 52000000, 30053627, 120000000, 200000000, "2000-01-05"),
                (3, "tt9000003", "movie", "Cedar Light", "", 2000, 95, "G", 8.5,
                 40000000, 10000000, 150000000, 300000000, "2000-01-09"),
                (4, "tt9000004", "movie", "Distant Gate", "", 2000, 80, "Not Rated", 9.5,
                 10000000, 9000000, 1000000, 100000000, "2000-01-10"),
                (5, "tt9000005", "movie", "Evening Road", "", 2012, 70, "G", 9.9,
                 10000000, 9000000, 1000000, 100000000, "2012-01-01"),
                (6, "tt9000006", "tvSeries", "Forest Signal", "", 2001, 30, "G", 9.9,
                 10000000, 9000000, 1000000, 100000000, "2001-01-01"),
            ])
            db.executemany("INSERT INTO persons VALUES (?,?,?)", [
                (1, "nm0000229", "Steven Spielberg"),
                (2, "nm0000158", "Tom Hanks"),
                (3, "nm0000138", "Leonardo DiCaprio"),
            ])
            credits = [(1, 1, "director"), (2, 1, "director"), (3, 1, "writer"),
                       (1, 2, "actor"), (2, 2, "actor"), (3, 2, "actor"),
                       (4, 2, "writer"), (6, 2, "actor"),
                       (1, 3, "actor"), (2, 3, "actor"), (3, 3, "actor"),
                       (4, 3, "director"), (6, 3, "actor")]
            db.executemany("INSERT INTO credits VALUES (?,?,?,?,?)",
                           [(i, title, person, role, i) for i, (title, person, role) in enumerate(credits, 1)])
            db.execute("INSERT INTO genres VALUES (1,'animation')")
            db.executemany("INSERT INTO title_genre VALUES (?,1)", [(i,) for i in range(1, 7)])
            db.execute("INSERT INTO users VALUES (1,'Synthetic account')")
            db.execute("INSERT INTO reviews VALUES (1,'Synthetic content')")
        shutil.copyfile(self.folder / "before.db", self.folder / "after.db")

    def mutate(self, sql, params=(), both=True):
        for filename in (["before.db", "after.db"] if both else ["after.db"]):
            with sqlite3.connect(self.folder / filename) as db:
                db.execute(sql, params)

    def check(self, task, answer=None, paths=None):
        paths = ["/title/tt9000001", "/title/tt9000002", "/title/tt9000003"] if paths is None else paths
        trajectory = {"task_id": f"IMDb--{task}", "start_url": self.origin + "/",
                      "final_answer": ANSWERS[task] if answer is None else answer,
                      "steps": [{"step": i, "url": self.origin + "/",
                                 "url_after": path if path.startswith("http") else self.origin + path,
                                 "status": "completed", "action": "navigate"}
                                for i, path in enumerate(paths)]}
        (self.folder / "trajectory.json").write_text(json.dumps(trajectory))
        with RunEvidence(self.folder, f"IMDb--{task}") as run:
            return grader.check_catalog_read_task(task, run)

    def reject(self, task, answer=None, paths=None):
        with self.assertRaises(VerificationError):
            self.check(task, answer, paths)

    def test_positive_tables_all_tasks(self):
        for task in ANSWERS:
            with self.subTest(task=task):
                self.assertTrue(self.check(task))

    def test_no_answer_noop_no_navigation_and_foreign_sources(self):
        for task in ANSWERS:
            with self.subTest(task=task):
                self.reject(task, "")
                self.reject(task, "Done.")
                self.reject(task, paths=[])
                self.reject(task, paths=["http://foreign.example/title/tt9000001",
                                         "http://foreign.example/title/tt9000002",
                                         "http://foreign.example/title/tt9000003"])

    def test_wrong_title_binding_and_partial_rows(self):
        for task in ANSWERS:
            with self.subTest(task=task):
                self.reject(task, ANSWERS[task].replace("| Amber Run |", "| Distant Gate |", 1))
                self.reject(task, "\n".join(line for line in ANSWERS[task].splitlines()
                                           if not line.startswith("| Bronze Tide |")))

    def test_any_business_table_mutation_rejected(self):
        for sql in ("UPDATE reviews SET body='Changed'", "UPDATE users SET name='Changed'",
                    "UPDATE titles SET year=2005 WHERE id=1",
                    "INSERT INTO watchlist_items VALUES (1,1)",
                    "INSERT INTO user_ratings VALUES (1,10)"):
            shutil.copyfile(self.folder / "before.db", self.folder / "after.db")
            self.mutate(sql, both=False)
            for task in ANSWERS:
                with self.subTest(sql=sql, task=task):
                    self.reject(task)

    def test_navigation_order_and_equivalent_credit_sources(self):
        for task in ANSWERS:
            self.assertTrue(self.check(task, paths=["/name/nm0000158", "/name/nm0000138",
                                                  "/title/tt9000003/", "/title/tt9000002/",
                                                  "/title/tt9000001/"]))

    def test_credit_outside_first_fifteen_needs_profile_or_fullcredits(self):
        for i in range(16):
            self.mutate("INSERT INTO credits VALUES (?,?,?,?,?)", (100+i, 1, 100+i, "actor", -i-1))
        self.reject(19)
        self.assertTrue(self.check(19, paths=["/title/tt9000001", "/title/tt9000002",
                                            "/title/tt9000001/fullcredits"]))

    def test_19_equivalent_units_and_prose(self):
        answer = ("Amber Run: budget USD 70 million; opening weekend $30,600,000; 43.7 percent.\n"
                  "Bronze Tide: budget $52 million; opening $30.1 million; 57.9%.\n"
                  "Bronze Tide has the largest percentage, while Amber Run is lower.")
        self.assertTrue(self.check(19, answer))

    def test_19_20_chinese_maximum_cue(self):
        for task, winner in ((19, "Bronze Tide"), (20, "Amber Run")):
            answer = ANSWERS[task].replace(f"Winner: {winner}", f"最高为 {winner}")
            with self.subTest(task=task):
                self.assertTrue(self.check(task, answer))

    def test_19_displayed_precision_required(self):
        self.reject(19, ANSWERS[19].replace("30.6M", "30,576,104"))
        self.reject(19, ANSWERS[19].replace("43.7%", "43.6%"))

    def test_19_swapped_fields_and_amounts(self):
        self.reject(19, ANSWERS[19].replace("$70.0M | $30.6M", "$30.6M | $70.0M"))
        self.reject(19, ANSWERS[19].replace("$30.6M", "$30.1M").replace("43.7%", "57.9%"))
        self.reject(19, ANSWERS[19].replace("Opening weekend US & Canada", "Gross worldwide"))

    def test_19_role_change_derives_new_snapshot_intersection(self):
        self.mutate("UPDATE credits SET role='writer' WHERE title_id=2 AND person_id=1")
        self.reject(19)
        self.assertTrue(self.check(19, "Amber Run: budget $70M; opening $30.6M; 43.7%.\nWinner: Amber Run."))

    def test_19_all_maximum_ties(self):
        self.mutate("UPDATE titles SET budget=70000000,box_office_opening=30576104 WHERE id=2")
        answer = ANSWERS[19].replace("52.0M", "70.0M").replace("30.1M", "30.6M").replace("57.9%", "43.7%")
        self.reject(19, answer)
        self.assertTrue(self.check(19, answer.replace("Winner: Bronze Tide (43.7%).", "Winners: Amber Run and Bronze Tide (43.7%).")))

    def test_19_false_or_unknown_extra_winner(self):
        self.reject(19, ANSWERS[19].replace("Winner: Bronze Tide", "Winners: Bronze Tide and Amber Run"))
        self.reject(19, ANSWERS[19].replace("Winner: Bronze Tide", "Winners: Bronze Tide and Imaginary Feature"))

    def test_20_false_winner_and_wrong_percent(self):
        self.reject(20, ANSWERS[20].replace("Winner: Amber Run", "Winner: Cedar Light"))
        self.reject(20, ANSWERS[20].replace("70.0%", "70.1%"))

    def test_20_reversed_fields_and_role_only_extra(self):
        self.reject(20, ANSWERS[20].replace("Gross US & Canada", "X").replace("Gross worldwide", "Gross US & Canada").replace("X", "Gross worldwide"))
        self.reject(20, ANSWERS[20] + "\nDistant Gate: domestic $1M; worldwide $100M; 99.0%.")
        self.assertTrue(self.check(20, ANSWERS[20] + "\nDistant Gate is excluded: it is a Director credit, not Actor."))

    def test_20_snapshot_gross_change_changes_truth(self):
        self.mutate("UPDATE titles SET box_office_us=60000000 WHERE id=1")
        self.reject(20)
        answer = ANSWERS[20].replace("$30.0M", "$60.0M").replace("70.0%", "40.0%")
        answer = answer.replace("Winner: Amber Run (40.0%).", "Winner: Cedar Light (50.0%).")
        self.assertTrue(self.check(20, answer))

    def test_20_tied_winners_are_complete(self):
        self.mutate("UPDATE titles SET box_office_us=90000000 WHERE id=3")
        answer = ANSWERS[20].replace("$150.0M", "$90.0M").replace("50.0%", "70.0%")
        self.reject(20, answer)
        self.assertTrue(self.check(20, answer.replace("Winner: Amber Run (70.0%).", "Winners: Amber Run and Cedar Light (70.0%).")))

    def test_unknown_extra_table_and_prose_rows(self):
        self.reject(20, ANSWERS[20].replace("| Bronze Tide |", "| Imaginary Feature |"))
        self.reject(20, ANSWERS[20] + "\nImaginary Feature: domestic $3M; worldwide $100M; 97.0%.")

    def test_prefix_titles_and_middle_dot_aliases(self):
        self.mutate("UPDATE titles SET primary_title='Toy Story' WHERE id=1")
        self.mutate("UPDATE titles SET primary_title='Toy Story 3' WHERE id=2")
        self.mutate("UPDATE titles SET primary_title='WALL·E' WHERE id=3")
        for task in ANSWERS:
            answer = ANSWERS[task].replace("Amber Run", "Toy Story").replace("Bronze Tide", "Toy Story 3").replace("Cedar Light", "WALL-E")
            self.assertTrue(self.check(task, answer))

    def test_18_pair_constraints_ties_and_bound_fields(self):
        for before, after in [("190 minutes", "191 minutes"), ("17.0", "17.1"),
                              ("90 minutes", "95 minutes"), ("| G |", "| PG-13 |")]:
            self.reject(18, ANSWERS[18].replace(before, after, 1))
        self.reject(18, ANSWERS[18].split("\nBest pair: Cedar")[0])
        self.reject(18, ANSWERS[18] + "\nBest pair: Bronze Tide + Cedar Light; total runtime 195 minutes; summed rating 17.0.")

    def test_18_hour_units_and_reversed_pairs(self):
        answer = ANSWERS[18].replace("| 90 minutes |", "| 1 hour 30 minutes |").replace("| 100 minutes |", "| 1h 40m |").replace("| 95 minutes |", "| 1 hour 35 minutes |")
        answer = answer.replace("190 minutes", "3 hours 10 minutes").replace("185 minutes", "3h 5m")
        self.assertTrue(self.check(18, answer))

    def test_18_mpaa_and_year_are_derived(self):
        self.mutate("UPDATE titles SET mpaa_rating='G' WHERE id=4")
        self.reject(18)

    def test_unknown_and_self_pairs_are_rejected(self):
        self.reject(18, ANSWERS[18] + "\nBest pair: Amber Run and Imaginary Feature; combined runtime 190 minutes; summed rating 17.0.")
        self.reject(18, ANSWERS[18] + "\nBest pair: Amber Run and Amber Run; combined runtime 180 minutes; summed rating 17.0.")
        self.reject(23, ANSWERS[23] + "\nClosest pair: Imaginary Feature and Cedar Light, 4 days.")

    def test_18_prose_film_facts_and_pair_table(self):
        answer = ("Amber Run: IMDb rating 8.5; runtime 90 minutes; MPAA G.\n"
                  "Bronze Tide: IMDb rating 8.5; runtime 100 minutes; MPAA PG.\n"
                  "Cedar Light: IMDb rating 8.5; runtime 95 minutes; MPAA G.\n\n"
                  "| First film | Second film | Combined runtime (min) | Summed rating |\n|---|---|---|---|\n"
                  "| Amber Run | Bronze Tide | 190 | 17 |\n| Amber Run | Cedar Light | 185 | 17 |")
        self.assertTrue(self.check(18, answer))

    def test_18_single_feature_table_then_separate_totals(self):
        self.mutate("UPDATE titles SET rating_avg=8.4 WHERE id=3")
        table = ("| Film | IMDb rating | Runtime | MPAA |\n|---|---|---|---|\n"
                 "| Amber Run | 8.5 | 90 minutes | G |\n"
                 "| Bronze Tide | 8.5 | 100 minutes | PG |\n")
        totals = "Combined runtime: 190 minutes.\nSummed rating: 17.0."
        for heading in ("The best double feature is:\n", "Best pair: Amber Run + Bronze Tide\n"):
            for separator in ("", "\n"):
                with self.subTest(heading=heading, separator=separator):
                    answer = heading + table + separator + totals
                    self.assertTrue(self.check(18, answer))
                    self.reject(18, answer.replace("190 minutes", "189 minutes"))
                    self.reject(18, answer.replace("17.0", "17.1"))

    def test_18_multi_pair_unattributed_totals_remain_ambiguous(self):
        table = ANSWERS[18].split("\n\nBest pair:")[0]
        answer = ("The best double features are:\n" + table + "\n\n"
                  "Combined runtime: 190 minutes.\nSummed rating: 17.0.\n"
                  "Combined runtime: 185 minutes.\nSummed rating: 17.0.")
        self.reject(18, answer)
        answer = ("Best pair: Amber Run + Bronze Tide\nBest pair: Amber Run + Cedar Light\n" + table +
                  "\nCombined runtime: 190 minutes.\nCombined runtime: 185 minutes.\nSummed rating: 17.0.")
        self.reject(18, answer)

    def test_18_chinese_equivalent_fields_totals_and_exclusion(self):
        self.mutate("UPDATE titles SET rating_avg=8.4 WHERE id=3")
        answer = ("最优组合只有一组：Amber Run（2000），IMDb 8.5，90分钟，MPAA G；"
                  "Bronze Tide（2000），IMDb 8.5，100分钟，MPAA PG。合计190分钟，评分合计17.0。"
                  "Distant Gate虽为9.5，但页面分级为Not Rated，不符合G/PG；因此没有并列最优组合。")
        self.assertTrue(self.check(18, answer))
        for before, after in (("合计190", "合计189"), ("评分合计17.0", "评分合计16.9"),
                              ("IMDb 8.5，90分钟", "IMDb 8.4，90分钟"),
                              ("不符合G/PG", "符合G/PG")):
            self.reject(18, answer.replace(before, after, 1))
        self.reject(18, answer.replace("90分钟", "TEMP").replace("100分钟", "90分钟").replace("TEMP", "100分钟"))

    def test_19_winner_flag_table(self):
        answer = ("| Film | Budget | Opening | Ratio (%) | Winner |\n|---|---|---|---|---|\n"
                  "| Bronze Tide | USD 52000000 | USD 30100000 | 57.9 | yes |\n"
                  "| Amber Run | USD 70000000 | USD 30600000 | 43.7 | no |")
        self.assertTrue(self.check(19, answer))

    def test_20_prose_and_short_domestic_column_alias(self):
        answer = ("Cedar Light: domestic gross $150 million; worldwide gross $300 million; 50 percent.\n"
                  "Amber Run: domestic gross USD 30000000; worldwide gross USD 100000000; 70 percent.\n"
                  "Bronze Tide: domestic gross $120M; worldwide $200M; 40 percent.\n"
                  "Amber Run has the largest percentage.")
        self.assertTrue(self.check(20, answer))
        self.assertTrue(self.check(20, ANSWERS[20].replace("Gross US & Canada", "US & Canada")))

    def test_23_written_dates_and_pair_table(self):
        answer = ("Amber Run: January 1st, 2000.\nBronze Tide: 5 January 2000.\n"
                  "Cedar Light: Jan 9, 2000.\n\n"
                  "| First film | Second film | Gap (days) |\n|---|---|---|\n"
                  "| Bronze Tide | Amber Run | 4 |\n| Cedar Light | Bronze Tide | 4 |")
        self.assertTrue(self.check(23, answer))

    def test_23_partial_ties_false_pair_and_wrong_gap(self):
        self.reject(23, ANSWERS[23].split("\nClosest pair: Bronze")[0])
        self.reject(23, ANSWERS[23] + "\nClosest pair: Amber Run to Cedar Light - 8 days.")
        self.reject(23, ANSWERS[23].replace("4 calendar days", "5 calendar days"))

    def test_23_date_swap_and_nonchronological_table(self):
        self.reject(23, ANSWERS[23].replace("2000-01-01", "2000-01-02"))
        self.reject(23, ANSWERS[23].replace("| Amber Run | 2000-01-01 |\n| Bronze Tide | 2000-01-05 |",
                                         "| Bronze Tide | 2000-01-05 |\n| Amber Run | 2000-01-01 |"))

    def test_23_dates_before_titles_and_repeated_pair_dates(self):
        answer = ("| Release date | Film |\n|---|---|\n| January 1, 2000 | Amber Run |\n"
                  "| January 5, 2000 | Bronze Tide |\n| January 9, 2000 | Cedar Light |\n\n"
                  "Closest pair: Amber Run (2000-01-01) to Bronze Tide (2000-01-05), 4 days.\n"
                  "Closest pair: Bronze Tide (2000-01-05) to Cedar Light (2000-01-09), 4 days.")
        self.assertTrue(self.check(23, answer))
        self.reject(23, answer.replace("Amber Run (2000-01-01) to Bronze Tide (2000-01-05)",
                                       "Amber Run (2000-01-05) to Bronze Tide (2000-01-01)"))

    def test_23_single_paragraph_timeline(self):
        answer = ("Timeline: Amber Run: January 1, 2000; Bronze Tide: January 5, 2000; Cedar Light: January 9, 2000.\n"
                  "Closest pair: Amber Run to Bronze Tide, 4 days.\nClosest pair: Bronze Tide to Cedar Light, 4 days.")
        self.assertTrue(self.check(23, answer))

    def test_23_same_date_order_is_not_an_id_tiebreaker(self):
        self.mutate("UPDATE titles SET release_date='2000-01-01' WHERE id IN (2,3)")
        answer = ("Cedar Light: January 1, 2000.\nAmber Run: January 1, 2000.\nBronze Tide: January 1, 2000.\n"
                  "Closest pair: Cedar Light and Amber Run, 0 days.\nClosest pair: Amber Run and Bronze Tide, 0 days.")
        self.assertTrue(self.check(23, answer))
        self.reject(23, answer + "\nClosest pair: Cedar Light and Bronze Tide, 0 days.")


if __name__ == "__main__":
    unittest.main()
