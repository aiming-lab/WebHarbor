"""Synthetic read-task checks; these fixtures are not real browser-run evidence.

The small catalog intentionally contains invented titles, reviews and ties.
It uses the app's table/column names without importing Flask or copying seed DBs.
"""

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
verify_lib = importlib.import_module("verify_lib")
read_tasks = importlib.import_module("read_tasks")
RunEvidence = verify_lib.RunEvidence
VerificationError = verify_lib.VerificationError
TASKS = {row["id"]: row for row in (
    json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines()
    if line.strip()
)}

SHAW = "tt0111161"
GOD = "tt0068646"
DARK = "tt0468569"
INCEPTION = "tt1375666"
PULP = "tt0110912"
ECHO = "tt9000000"
SERIES = "tt9000001"
NOLAN = "nm0634240"
BALE = "nm0000288"

DRAMA_SEARCH = (
    "/search/title?title_type=movie&genre=drama&rating_min=8.5&sort=rating"
)
CRIME_SEARCH = (
    "/search/title?title_type=movie&genre=crime&year_from=1990&year_to=1999"
    "&rating_min=8.5&sort=rating"
)

SCHEMA = """
CREATE TABLE titles (
    id INTEGER PRIMARY KEY, tt_id TEXT UNIQUE, title_type TEXT,
    primary_title TEXT, original_title TEXT DEFAULT '', year INTEGER,
    end_year INTEGER, runtime_min INTEGER, mpaa_rating TEXT,
    plot_short TEXT DEFAULT '', plot TEXT DEFAULT '', rating_avg REAL,
    num_votes INTEGER DEFAULT 100, metascore INTEGER, popularity_rank INTEGER,
    top_rank INTEGER, box_office_us INTEGER, box_office_world INTEGER,
    box_office_opening INTEGER, budget INTEGER, release_date TEXT DEFAULT '',
    country TEXT DEFAULT '', language TEXT DEFAULT '', poster_path TEXT DEFAULT '',
    taglines_json TEXT DEFAULT '[]'
);
CREATE TABLE persons (
    id INTEGER PRIMARY KEY, nm_id TEXT UNIQUE, name TEXT, birth_year INTEGER,
    death_year INTEGER, birth_place TEXT DEFAULT '', bio TEXT DEFAULT '',
    primary_profession TEXT DEFAULT '', photo_path TEXT DEFAULT '',
    known_for_json TEXT DEFAULT '[]'
);
CREATE TABLE genres (id INTEGER PRIMARY KEY, name TEXT, slug TEXT UNIQUE);
CREATE TABLE title_genre (title_id INTEGER, genre_id INTEGER,
    PRIMARY KEY (title_id, genre_id));
CREATE TABLE credits (
    id INTEGER PRIMARY KEY, title_id INTEGER, person_id INTEGER,
    role TEXT, character TEXT DEFAULT '', billing_order INTEGER
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY, email TEXT, name TEXT, password_hash TEXT,
    created_at TEXT
);
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY, title_id INTEGER, user_id INTEGER, rating INTEGER,
    headline TEXT, body TEXT, helpful_count INTEGER, created_at TEXT, is_seed INTEGER
);
CREATE TABLE user_ratings (
    id INTEGER PRIMARY KEY, user_id INTEGER, title_id INTEGER,
    rating INTEGER, created_at TEXT
);
CREATE TABLE watchlist_items (
    id INTEGER PRIMARY KEY, user_id INTEGER, title_id INTEGER, added_at TEXT
);
"""

# The numeric facts are fixture inputs, not claims about the live IMDb website.
TITLES = [
    (1, SHAW, "movie", "The Shawshank Redemption", 1994, 142, "R", 9.3, 1,
     28767189, 28884504, 727327, 25000000),
    (2, GOD, "movie", "The Godfather", 1972, 175, "R", 9.2, 2,
     136381073, 246120974, 302393, 6000000),
    (3, DARK, "movie", "The Dark Knight", 2008, 152, "PG-13", 9.0, 3,
     534858444, 1005973645, 158411483, 185000000),
    (4, INCEPTION, "movie", "Inception", 2010, 148, "PG-13", 8.8, 6,
     292576195, 836848102, 62785337, 160000000),
    (5, PULP, "movie", "Pulp Fiction", 1994, 154, "R", 8.9, 4,
     107928762, 213928762, 93117882, 8000000),
    (6, ECHO, "movie", "Synthetic Cutoff Echo", 1999, 100, "R", 8.9, 5,
     15000000, 32500000, 2000000, 4500000),
    (7, SERIES, "tvSeries", "Synthetic Crime Series", 2008, 45, "TV-MA", 9.5, 1,
     None, None, None, None),
    (8, "tt9000002", "tvSeries", "Synthetic Nolan Television", 2020, 50,
     "TV-MA", 9.9, 2, None, None, None, None),
    (9, "tt9000003", "movie", "Synthetic Writer Only Feature", 2021, 90,
     "PG", 9.7, None, 1000000, 3000000, 100000, 500000),
]

ANSWERS = {
    0: ("#1 The Shawshank Redemption: 142 minutes, R.\n"
        "#3 The Dark Knight: 152 minutes, PG-13.\n"
        "The Dark Knight has the longer runtime."),
    2: "The Dark Knight is first in cumulative domestic gross; production budget $185 million.",
    3: ("The Shawshank Redemption: production budget $25.0M; "
        "Opening weekend US & Canada $727.3K."),
    4: "The Godfather: directed by Francis Ford Coppola; worldwide gross $246.1M.",
    7: "The Dark Knight (2008), IMDb rating 9.0/10.",
    8: "Christian Bale plays Bruce Wayne; his birth year is 1974.",
    9: "1. The Shawshank Redemption\n2. The Godfather\n3. The Dark Knight",
    10: "The Shawshank Redemption: directed by Frank Darabont; worldwide gross $28.9M.",
    12: ("Movie: The Shawshank Redemption (1994), IMDb rating 9.3.\n"
         "TV series: Synthetic Crime Series (2008), IMDb rating 9.5.\n"
         "The TV series group has the higher top rating."),
    14: ("The Dark Knight: IMDb rating 9.0; worldwide gross $1.0B.\n"
         "Inception: IMDb rating 8.8; worldwide gross $836.8M.\n"
         "The Dark Knight has the higher rating and the larger gross."),
}

PATHS = {
    0: ["/chart/top", f"/title/{DARK}", f"/title/{SHAW}"],
    2: ["/chart/boxoffice", f"/title/{DARK}"],
    3: [f"/title/{SHAW}"],
    4: [f"/title/{GOD}"],
    7: [f"/name/{NOLAN}", f"/title/{DARK}", f"/title/{INCEPTION}"],
    8: [f"/title/{DARK}", f"/name/{BALE}"],
    9: [DRAMA_SEARCH],
    10: [CRIME_SEARCH, f"/title/{SHAW}"],
    12: ["/genre/crime", f"/title/{SHAW}", f"/title/{SERIES}"],
    14: [f"/title/{INCEPTION}", f"/title/{DARK}"],
}


class SyntheticReadTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name)
        self.origin = "http://synthetic-read.localhost:48015"
        before = self.run_dir / "before.db"
        with sqlite3.connect(before) as db:
            db.executescript(SCHEMA)
            db.executemany(
                "INSERT INTO titles (id,tt_id,title_type,primary_title,year,"
                "runtime_min,mpaa_rating,rating_avg,top_rank,box_office_us,"
                "box_office_world,box_office_opening,budget) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", TITLES)
            db.executemany("INSERT INTO persons (id,nm_id,name,birth_year) VALUES (?,?,?,?)", [
                (1, "nm0001104", "Frank Darabont", 1959),
                (2, "nm0000338", "Francis Ford Coppola", 1939),
                (3, NOLAN, "Christopher Nolan", 1970),
                (4, BALE, "Christian Bale", 1974),
                (5, "nm0005132", "Heath Ledger", 1979),
                (6, "nm0000233", "Quentin Tarantino", 1963),
                (7, "nm9000001", "Synthetic Director", 1960),
            ])
            db.executemany("INSERT INTO genres VALUES (?,?,?)", [
                (1, "Drama", "drama"), (2, "Crime", "crime"), (3, "Action", "action")])
            db.executemany("INSERT INTO title_genre VALUES (?,?)", [
                (1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2),
                (4, 1), (4, 3), (5, 1), (5, 2), (6, 1), (6, 2),
                (7, 1), (7, 2), (8, 3), (9, 3),
            ])
            db.executemany(
                "INSERT INTO credits (title_id,person_id,role,character,billing_order) "
                "VALUES (?,?,?,?,?)", [
                    (1, 1, "director", "", None),
                    (2, 2, "director", "", None),
                    (3, 3, "director", "", None),
                    (4, 3, "director", "", None),
                    (5, 6, "director", "", None),
                    (6, 7, "director", "", None),
                    (8, 3, "director", "", None),
                    (9, 3, "writer", "", None),
                    (9, 7, "director", "", None),
                    (3, 5, "actor", "Joker", 2),
                    (3, 4, "actor", "Bruce Wayne", 1),
                ])
            db.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
                (1, "synthetic-alice@example.test", "Synthetic Alice", "fixture-hash", "2020-01-01"),
                (2, "synthetic-bob@example.test", "Synthetic Bob", "fixture-hash", "2020-01-01"),
            ])
        shutil.copyfile(before, self.run_dir / "after.db")

    def edit_catalog(self, sql, parameters=()):
        """Change both snapshots: task truth changes, but business state does not."""
        for filename in ("before.db", "after.db"):
            with sqlite3.connect(self.run_dir / filename) as db:
                db.execute(sql, parameters)

    def check(self, number, answer=None, paths=None):
        task_id = f"IMDb--{number}"
        selected_paths = PATHS[number] if paths is None else paths
        trajectory = {
            "task_id": task_id,
            "task": TASKS[task_id]["ques"],
            "start_url": self.origin + "/",
            "final_answer": ANSWERS[number] if answer is None else answer,
            "fixture_kind": "synthetic",
            "steps": [{"url": path if "://" in path else self.origin + path,
                       "status": "completed", "action": "observe"}
                      for path in selected_paths],
        }
        (self.run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        with RunEvidence(self.run_dir, task_id, expected_ques=TASKS[task_id]["ques"]) as run:
            return read_tasks.check_read_task(number, run)

    def assert_accepts(self, number, answer=None, paths=None):
        self.assertIsInstance(self.check(number, answer, paths), list)

    def assert_rejects(self, number, answer=None, paths=None):
        with self.assertRaises(VerificationError):
            self.check(number, answer, paths)

    def test_task0_ranked_films_can_be_visited_in_either_order(self):
        self.assert_accepts(0)
        self.assert_accepts(0, paths=["/chart/top", f"/title/{SHAW}", f"/title/{DARK}"])

    def test_task2_uses_catalog_cumulative_domestic_gross(self):
        self.assert_accepts(2)
        # A larger opening weekend does not change the cumulative chart winner.
        self.edit_catalog("UPDATE titles SET box_office_opening=999000000 WHERE tt_id=?", (PULP,))
        self.assert_accepts(2)

    def test_task3_budget_and_opening_are_distinct_labeled_values(self):
        self.assert_accepts(3)

    def test_task4_director_and_worldwide_gross(self):
        self.assert_accepts(4)
        self.assert_accepts(4, paths=[f"/title/{GOD}/fullcredits", f"/title/{GOD}"])

    def test_task7_director_movies_exclude_writer_credit_and_tv(self):
        self.assert_accepts(7)

    def test_task8_first_billed_cast_and_birth_year(self):
        self.assert_accepts(8)
        self.assert_accepts(8, paths=[f"/title/{DARK}/fullcredits", f"/name/{BALE}"])

    def test_task9_top_three_from_results_page(self):
        self.assert_accepts(9)

    def test_task10_crime_nineties_director_and_worldwide(self):
        self.assert_accepts(10)

    def test_task12_compares_movie_and_tv_top_ratings(self):
        self.assert_accepts(12)

    def test_task14_values_and_both_comparisons_in_either_visit_order(self):
        self.assert_accepts(14)
        self.assert_accepts(14, paths=list(reversed(PATHS[14])))

    def test_every_read_task_requires_relevant_navigation(self):
        for number in ANSWERS:
            with self.subTest(number=number):
                self.assert_rejects(number, paths=[])

    def test_foreign_urls_cannot_supply_the_required_navigation(self):
        for number, paths in PATHS.items():
            with self.subTest(number=number):
                self.assert_rejects(number, paths=["http://foreign.example" + path for path in paths])

    def test_every_read_task_rejects_business_state_changes(self):
        with sqlite3.connect(self.run_dir / "after.db") as db:
            db.execute("UPDATE users SET name='Unexpected edit' WHERE id=1")
        for number in ANSWERS:
            with self.subTest(number=number):
                self.assert_rejects(number)

    def test_wrong_or_partial_answers_are_rejected(self):
        examples = {
            0: "The Shawshank Redemption: 152 minutes, PG-13.\nThe Dark Knight: 142 minutes, R.\nThe Shawshank Redemption is longer.",
            2: "The Godfather ranks first; budget $6 million.",
            3: "The Shawshank Redemption: production budget $25 million.",
            4: "The Godfather: Francis Ford Coppola directed it.",
            7: "Synthetic Writer Only Feature (2021), rating 9.7.",
            8: "Christian Bale plays Bruce Wayne; he was born in Wales.",
            9: "The Godfather\nThe Dark Knight\nPulp Fiction",
            10: "The Shawshank Redemption: worldwide gross $28.9M.",
            12: "Movie: The Shawshank Redemption (1994), rating 9.5.\nTV: Synthetic Crime Series (2008), rating 9.3.\nMovies have the higher rating.",
            14: "The Dark Knight: rating 9.0, worldwide gross $836.8M.\nInception: rating 8.8, worldwide gross $1.0B.\nThe Dark Knight has the higher rating; Inception has the larger gross.",
        }
        for number, answer in examples.items():
            with self.subTest(number=number):
                self.assert_rejects(number, answer)

    def test_money_accepts_exact_amounts_and_equivalent_units(self):
        answers = [
            "The Shawshank Redemption: budget USD 25,000,000; opening weekend US & Canada USD 727,327.",
            "The Shawshank Redemption: budget 25 million dollars; opening weekend US & Canada 727.3 thousand dollars.",
            "The Shawshank Redemption: budget $25000K; opening weekend US & Canada $0.7273M.",
        ]
        for answer in answers:
            with self.subTest(answer=answer):
                self.assert_accepts(3, answer)

    def test_money_labels_cannot_be_swapped_or_omitted(self):
        for answer in (
            "The Shawshank Redemption: production budget $727.3K; opening weekend US & Canada $25M.",
            "The Shawshank Redemption: $25M and $727.3K.",
        ):
            with self.subTest(answer=answer):
                self.assert_rejects(3, answer)

    def test_markdown_rows_preserve_runtime_and_classification_binding(self):
        self.assert_accepts(0, """| Rank | Title | Runtime | MPAA |
| --- | --- | --- | --- |
| 1 | The Shawshank Redemption | 142 minutes | R |
| 3 | The Dark Knight | 152 minutes | PG-13 |

The Dark Knight has the longer runtime.
""")

    def test_markdown_money_columns_and_explicit_comparisons(self):
        self.assert_accepts(14, """| Field | The Dark Knight | Inception |
| --- | --- | --- |
| IMDb rating | 9.0 | 8.8 |
| Worldwide gross | $1.0 billion | $836.8 million |

The Dark Knight has the higher IMDb rating and the larger worldwide gross.
""")

    def test_catalog_changes_drive_truth_instead_of_hardcoded_answers(self):
        self.edit_catalog("UPDATE titles SET budget=187000000 WHERE tt_id=?", (DARK,))
        self.assert_rejects(2)
        self.assert_accepts(2, "The Dark Knight is first; production budget $187M.")
        self.edit_catalog("UPDATE persons SET birth_year=1975 WHERE nm_id=?", (BALE,))
        self.assert_rejects(8)
        self.assert_accepts(8, "Christian Bale plays Bruce Wayne; his birth year is 1975.")

    def test_task0_requires_both_title_details_and_chart(self):
        for paths in (["/chart/top", f"/title/{SHAW}"], [f"/title/{SHAW}", f"/title/{DARK}"]):
            with self.subTest(paths=paths):
                self.assert_rejects(0, paths=paths)

    def test_task0_explicit_word_ranks_keep_their_title_binding(self):
        answer = ("First-ranked movie: The Shawshank Redemption, 142 minutes, R.\n"
                  "Third-ranked movie: The Dark Knight, 152 minutes, PG-13.\n"
                  "The Dark Knight has the longer runtime.")
        self.assert_accepts(0, answer)
        self.assert_rejects(0, answer.replace("First-ranked", "Third-ranked", 1)
                            .replace("Third-ranked movie: The Dark Knight", "First-ranked movie: The Dark Knight"))
        table = ("| Rank | Title | Runtime | MPAA |\n| --- | --- | --- | --- |\n"
                 "| 3 | The Shawshank Redemption | 142 minutes | R |\n"
                 "| 1 | The Dark Knight | 152 minutes | PG-13 |\n"
                 "The Dark Knight has the longer runtime.")
        self.assert_rejects(0, table)

    def test_explicit_director_assertions_reject_extra_people(self):
        self.assert_rejects(4, "The Godfather: directed by Francis Ford Coppola and Christopher Nolan; worldwide gross $246.1M.")
        self.assert_rejects(4, "The Godfather: directed by Francis Ford Coppola and John Example; worldwide gross $246.1M.")
        self.assert_rejects(4, "The Godfather: directors: Francis Ford Coppola, John Example; worldwide gross $246.1M.")
        self.assert_rejects(10, "The Shawshank Redemption: directors are Frank Darabont and Christopher Nolan; worldwide gross $28.9M.")
        self.assert_accepts(4, "The Godfather: directed by Coppola, not Christopher Nolan; worldwide gross $246.1M.")
        self.assert_accepts(4, "The Godfather: directed by Francis Ford Coppola, not John Example; worldwide gross $246.1M.")
        self.assert_accepts(4, "The Godfather: directed by Francis Ford Coppola rather than Christopher Nolan; worldwide gross $246.1M.")
        self.assert_accepts(4, ANSWERS[4] + "\nChristopher Nolan directed Inception.")
        self.assert_accepts(10, ANSWERS[10] + "\nPulp Fiction was directed by Quentin Tarantino, but is a lower-rated result.")

    def test_director_full_names_do_not_match_unrelated_surnames(self):
        self.edit_catalog("INSERT INTO persons (id,nm_id,name) VALUES (8,'nm9000008','Clive Francis')")
        self.edit_catalog("INSERT INTO persons (id,nm_id,name) VALUES (9,'nm9000009','Caroline Quentin')")
        self.assert_accepts(4)
        self.edit_catalog("UPDATE titles SET rating_avg=9.4 WHERE tt_id=?", (PULP,))
        self.assert_accepts(10, "Pulp Fiction: directed by Quentin Tarantino; worldwide gross $213.9M.",
                            [CRIME_SEARCH, f"/title/{PULP}"])

    def test_highest_result_sets_reject_extra_winners_not_loser_explanations(self):
        extra = "Pulp Fiction: directed by Quentin Tarantino; worldwide gross $213.9M."
        self.assert_rejects(10, "Highest-rated matches:\n" + ANSWERS[10] + "\n" + extra)
        self.assert_rejects(10, ANSWERS[10] + "\nPulp Fiction is also tied for the highest rating.")
        self.assert_accepts(10, ANSWERS[10] + "\nPulp Fiction is not tied for the highest rating.")
        self.assert_accepts(10, "Highest-rated matches:\n" + ANSWERS[10]
                            + "\nPulp Fiction is a lower-rated candidate, not a highest-rated match.")
        self.assert_accepts(10, "Highest-rated matches:\n" + ANSWERS[10]
                            + "\n\nOther results:\n" + extra)
        false_movie = ("Top movies: The Shawshank Redemption (1994), IMDb rating 9.3.\n"
                       "Top movies: The Godfather (1972), IMDb rating 9.2.\n"
                       "TV series: Synthetic Crime Series (2008), IMDb rating 9.5.\n"
                       "The TV series group has the higher top rating.")
        self.assert_rejects(12, false_movie)
        self.assert_accepts(12, ANSWERS[12] + "\nThe Godfather (1972), rating 9.2, is below the highest-rated movie.")
        self.assert_accepts(12, ANSWERS[12] + "\nThe Godfather is not tied for highest.")

    def test_task7_all_director_movie_rating_ties(self):
        self.edit_catalog("UPDATE titles SET rating_avg=9.0 WHERE tt_id=?", (INCEPTION,))
        self.assert_rejects(7)
        self.assert_accepts(7, "The Dark Knight (2008): 9.0.\nInception (2010): 9.0.")
        self.assert_rejects(7, "The Dark Knight (2010): 9.0.\nInception (2008): 9.0.")

    def test_task8_requires_same_actor_profile_and_correct_character(self):
        self.assert_rejects(8, paths=[f"/title/{DARK}", "/name/nm0005132"])
        self.assert_rejects(8, "Christian Bale plays Joker; born 1974.")

    def test_task9_filters_must_all_be_present_and_correct(self):
        for query in (
            DRAMA_SEARCH.replace("title_type=movie&", ""),
            DRAMA_SEARCH.replace("genre=drama&", ""),
            DRAMA_SEARCH.replace("rating_min=8.5&", ""),
            DRAMA_SEARCH.replace("sort=rating", "sort=popularity"),
            DRAMA_SEARCH.replace("title_type=movie", "title_type=tvSeries"),
            DRAMA_SEARCH.replace("genre=drama", "genre=crime"),
            DRAMA_SEARCH.replace("rating_min=8.5", "rating_min=8.0"),
            DRAMA_SEARCH + "&genre=crime",
        ):
            with self.subTest(query=query):
                self.assert_rejects(9, paths=[query])
        self.assert_accepts(9, paths=[DRAMA_SEARCH.replace("8.5", "8.50")])

    def test_task9_requires_exactly_three_in_descending_order(self):
        for answer in (
            "The Shawshank Redemption\nThe Godfather",
            "The Dark Knight\nThe Godfather\nThe Shawshank Redemption",
            "The Shawshank Redemption\nThe Godfather\nThe Dark Knight\nPulp Fiction",
        ):
            with self.subTest(answer=answer):
                self.assert_rejects(9, answer)

    def test_task9_any_third_place_tie_selection_keeps_all_higher_titles(self):
        # Bring the third movie into the existing 8.9 cutoff tie.
        self.edit_catalog("UPDATE titles SET rating_avg=8.9 WHERE tt_id=?", (DARK,))
        for third in ("The Dark Knight", "Pulp Fiction", "Synthetic Cutoff Echo"):
            with self.subTest(third=third):
                self.assert_accepts(9, "The Shawshank Redemption\nThe Godfather\n" + third)
        self.assert_rejects(9, "The Shawshank Redemption\nPulp Fiction\nSynthetic Cutoff Echo")

    def test_task9_order_within_an_included_tie_is_irrelevant(self):
        self.edit_catalog("UPDATE titles SET rating_avg=9.2 WHERE tt_id=?", (DARK,))
        self.assert_accepts(9, "The Shawshank Redemption\nThe Dark Knight\nThe Godfather")

    def test_task10_all_search_constraints_are_required(self):
        for query in (
            CRIME_SEARCH.replace("year_from=1990&", ""),
            CRIME_SEARCH.replace("year_to=1999&", ""),
            CRIME_SEARCH.replace("year_from=1990", "year_from=1991"),
            CRIME_SEARCH.replace("year_to=1999", "year_to=1998"),
            CRIME_SEARCH.replace("genre=crime", "genre=drama"),
            CRIME_SEARCH.replace("rating_min=8.5", "rating_min=9.0"),
            CRIME_SEARCH.replace("sort=rating", "sort=year"),
        ):
            with self.subTest(query=query):
                self.assert_rejects(10, paths=[query, f"/title/{SHAW}"])

    def test_task10_inclusive_year_endpoints_and_all_top_ties(self):
        self.edit_catalog("UPDATE titles SET year=1990 WHERE tt_id=?", (SHAW,))
        self.edit_catalog("UPDATE titles SET rating_avg=9.3 WHERE tt_id=?", (ECHO,))
        paths = [CRIME_SEARCH, f"/title/{SHAW}", f"/title/{ECHO}"]
        self.assert_rejects(10, paths=paths)
        self.assert_accepts(10, ANSWERS[10] + "\nSynthetic Cutoff Echo: directed by Synthetic Director; worldwide gross $32.5M.", paths)

    def test_task10_all_directors_must_be_reported(self):
        self.edit_catalog("INSERT INTO credits (title_id,person_id,role) VALUES (1,7,'director')")
        self.assert_rejects(10)
        self.assert_accepts(10, "The Shawshank Redemption: directed by Frank Darabont and Synthetic Director; worldwide gross $28.9M.")

    def test_task12_all_within_group_ties_and_tied_comparison(self):
        self.edit_catalog("UPDATE titles SET rating_avg=9.3 WHERE tt_id IN (?,?)", (GOD, SERIES))
        answer = ("Movies: The Shawshank Redemption (1994), rating 9.3.\n"
                  "Movie: The Godfather (1972), rating 9.3.\n"
                  "TV series: Synthetic Crime Series (2008), rating 9.3.\n"
                  "The movie and TV series groups are tied at 9.3.")
        self.assert_accepts(12, answer)
        self.assert_rejects(12, answer.replace("Movie: The Godfather (1972), rating 9.3.\n", ""))

    def test_task12_wrong_comparison_cannot_hide_behind_correct_values(self):
        answer = ANSWERS[12].replace("TV series group has the higher", "movie group has the higher")
        self.assert_rejects(12, answer)

    def test_task14_ties_are_reported_explicitly(self):
        self.edit_catalog("UPDATE titles SET rating_avg=9.0, box_office_world=1005973645 WHERE tt_id=?", (INCEPTION,))
        answer = ("The Dark Knight: IMDb rating 9.0; worldwide gross $1.0B.\n"
                  "Inception: IMDb rating 9.0; worldwide gross $1.0B.\n"
                  "Both movies tie in rating and worldwide gross.")
        self.assert_accepts(14, answer)
        self.assert_rejects(14, answer.replace("Both movies tie in rating and worldwide gross.",
                                            "The Dark Knight has the higher rating and larger gross."))

    def test_fields_on_another_title_cannot_complete_the_winner(self):
        self.assert_rejects(10, "The Shawshank Redemption is the highest-rated result.\n"
                               "Pulp Fiction: directed by Frank Darabont; worldwide gross $28.9M.")
        self.assert_rejects(2, "The Dark Knight is first. Inception: production budget $185M.")
        self.assert_rejects(3, "The Godfather: budget $25M; opening weekend $727.3K.")
        self.assert_rejects(4, "The Godfather was selected.\n"
                              "Pulp Fiction: Francis Ford Coppola, worldwide gross $246.1M.")

    def test_comparison_in_second_clause_keeps_its_own_subject(self):
        facts = ANSWERS[14].rsplit("\n", 1)[0]
        for comparison in (
            "The Dark Knight has the higher rating, while Inception has the larger worldwide gross.",
            "The Dark Knight has the higher rating and Inception has the larger worldwide gross.",
            "The Dark Knight has the higher rating; Inception has the larger worldwide gross.",
        ):
            with self.subTest(comparison=comparison):
                self.assert_rejects(14, facts + "\n" + comparison)
        self.assert_accepts(14, facts + "\nThe Dark Knight has the higher rating than Inception and the larger worldwide gross.")
        self.assert_accepts(14, facts + "\nInception has a lower rating and a smaller worldwide gross than The Dark Knight.")

    def test_comparison_winner_table_and_missing_conclusion(self):
        facts = ANSWERS[14].rsplit("\n", 1)[0]
        table = "\n| Metric | Winner |\n| --- | --- |\n| Rating | The Dark Knight |\n| Worldwide gross | The Dark Knight |"
        self.assert_accepts(14, facts + table)
        self.assert_rejects(14, facts + table.replace("| Worldwide gross | The Dark Knight |", "| Worldwide gross | Inception |"))
        self.assert_rejects(14, facts)
        self.assert_rejects(0, ANSWERS[0].rsplit("\n", 1)[0])
        self.assert_rejects(12, ANSWERS[12].rsplit("\n", 1)[0])

    def test_extra_false_rating_tie_is_not_accepted(self):
        self.assert_rejects(7, "The Dark Knight (2008), IMDb rating 9.0/10.\n"
                              "Inception (2010), IMDb rating 9.0/10.\nThese films tie for the highest rating.")
        self.assert_accepts(7, "The Dark Knight (2008), IMDb rating 9.0/10.\n"
                              "Inception (2010) has a lower rating of 8.8/10.")

    def test_correct_negative_tie_explanation_is_allowed(self):
        self.assert_accepts(7, "The Dark Knight (2008), IMDb rating 9.0/10.\n"
                              "Inception (2010), IMDb rating 8.8/10; it is not tied for the highest rating.")
        self.assert_rejects(7, "The Dark Knight (2008), IMDb rating 9.0/10.\n"
                              "Inception (2010), IMDb rating 8.8/10; it is not higher, but is tied for highest.")

    def test_director_rating_can_come_from_other_public_listings(self):
        for page in ("/chart/boxoffice", "/chart/top", "/", "/find?q=Nolan&s=tt", DRAMA_SEARCH):
            with self.subTest(page=page):
                self.assert_accepts(7, paths=[f"/name/{NOLAN}", page])
        self.edit_catalog("UPDATE persons SET known_for_json=? WHERE nm_id=?", (json.dumps([DARK]), NOLAN))
        self.assert_accepts(7, paths=[f"/name/{NOLAN}"])

    def test_empty_advanced_results_do_not_prove_a_director_movie_rating(self):
        self.assert_rejects(7, paths=[f"/name/{NOLAN}", DRAMA_SEARCH + "&genre=drama"])
        self.assert_rejects(7, paths=[f"/name/{NOLAN}", DRAMA_SEARCH.replace("8.5", "9.5")])

    def test_actor_character_and_birth_year_bind_to_the_same_actor(self):
        self.assert_rejects(8, "Christian Bale plays Joker.\nHeath Ledger plays Bruce Wayne and was born in 1974.")
        self.assert_rejects(8, "Christian Bale plays Bruce Wayne and was born in 1979.\nHeath Ledger was born in 1974.")

    def test_multi_line_fact_blocks_and_group_headings(self):
        self.assert_accepts(14, "The Dark Knight\nIMDb rating: 9.0\nWorldwide gross: $1 billion\n\n"
                               "Inception\nIMDb rating: 8.8\nWorldwide gross: $836.8 million\n\n"
                               "The Dark Knight wins both comparisons.")
        self.assert_accepts(12, "Movies:\nThe Shawshank Redemption (1994): rating 9.3.\n\n"
                               "TV series:\nSynthetic Crime Series (2008): rating 9.5.\n\n"
                               "The TV group has the higher top rating.")

    def test_filter_duplicate_and_equivalent_query_values(self):
        for query in (DRAMA_SEARCH + "&genre=drama", DRAMA_SEARCH + "&rating_min=9.0",
                      DRAMA_SEARCH + "&title_type=tvSeries", DRAMA_SEARCH + "&year_to=2000"):
            with self.subTest(query=query):
                self.assert_rejects(9, paths=[query])
        self.assert_accepts(9, paths=[DRAMA_SEARCH + "&rating_min=8.50&year_from=&year_to="])


if __name__ == "__main__":
    unittest.main()
