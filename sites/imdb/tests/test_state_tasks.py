"""Synthetic state-task fixtures, not real browser runs or authenticity evidence.

Small local SQLite snapshots and params-based browser steps exercise the public
state-task verifier. No Flask server, seed database or old case verifier is used.
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
state_tasks = importlib.import_module("state_tasks")
RunEvidence = verify_lib.RunEvidence
VerificationError = verify_lib.VerificationError
TASKS = {task["id"]: task for task in (
    json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines()
    if line.strip()
)}

ORBIT = "tt9100001"
CRIME = "tt9100007"
INTERSTELLAR = "tt0816692"
EMAILS = {1: "bob.c@test.com", 2: "carol.d@test.com", 3: "alice.j@test.com",
          4: "other@example.test"}
USERS = {15: 1, 16: 2, 17: 3}
ANSWERS = {
    15: "Alpha Orbit (1990), Sci-Fi, was removed and is no longer in Bob's Watchlist.",
    16: "Alpha Crime (2020) is now rated 8/10 in Carol's My ratings.",
    17: ("Submitted Brilliant sci-fi epic for Interstellar (2014), rated 10/10. "
         "The new review appears on Interstellar's user reviews page."),
}

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT,
    password_hash TEXT, created_at TEXT);
CREATE TABLE titles (id INTEGER PRIMARY KEY, tt_id TEXT UNIQUE, title_type TEXT,
    primary_title TEXT, original_title TEXT DEFAULT '', year INTEGER,
    end_year INTEGER, rating_avg REAL DEFAULT 7.0, num_votes INTEGER DEFAULT 100,
    runtime_min INTEGER DEFAULT 100, mpaa_rating TEXT DEFAULT 'PG-13');
CREATE TABLE genres (id INTEGER PRIMARY KEY, name TEXT, slug TEXT);
CREATE TABLE title_genre (title_id INTEGER, genre_id INTEGER,
    PRIMARY KEY(title_id,genre_id));
CREATE TABLE watchlist_items (id INTEGER PRIMARY KEY, user_id INTEGER,
    title_id INTEGER, added_at TEXT);
CREATE TABLE user_ratings (id INTEGER PRIMARY KEY, user_id INTEGER,
    title_id INTEGER, rating INTEGER, created_at TEXT);
CREATE TABLE reviews (id INTEGER PRIMARY KEY, title_id INTEGER, user_id INTEGER,
    rating INTEGER, headline TEXT, body TEXT, helpful_count INTEGER,
    created_at TEXT, is_seed INTEGER);
CREATE TABLE news_items (id INTEGER PRIMARY KEY, headline TEXT, summary TEXT,
    source TEXT, published_at TEXT, category TEXT, related_tt TEXT);
"""

TITLES = [
    (1, ORBIT, "tvSeries", "Alpha Orbit", 1990),
    (2, "tt9100002", "tvSeries", "Beta Realm", 1990),
    (3, "tt9100003", "tvSeries", "Later Both", 2000),
    (4, "tt9100004", "tvSeries", "Old Crime Show", 1980),
    (5, "tt9100005", "movie", "Earlier Fantasy Movie", 1970),
    (6, "tt9100006", "tvSeries", "Unwatched Ancient", 1960),
    (7, CRIME, "movie", "Alpha Crime", 2020),
    (8, "tt9100008", "movie", "Beta Crime", 2020),
    (9, "tt9100009", "movie", "Already Eight", 2023),
    (10, "tt9100010", "movie", "Old Crime Film", 2010),
    (11, "tt9100011", "tvSeries", "Newest Crime Show", 2024),
    (12, "tt9100012", "movie", "Latest Drama Film", 2025),
    (13, "tt9100013", "movie", "Outside Crime", 2026),
    (14, INTERSTELLAR, "movie", "Interstellar", 2014),
]


class SyntheticStateTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name)
        self.origin = "http://synthetic-state.localhost:48015"
        with sqlite3.connect(self.run_dir / "before.db") as db:
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
                (user_id, email, {1: "Bob", 2: "Carol", 3: "Alice", 4: "Other"}[user_id],
                 "synthetic-password-hash", "2024-01-01 00:00:00")
                for user_id, email in EMAILS.items()
            ])
            db.executemany("INSERT INTO titles (id,tt_id,title_type,primary_title,year) VALUES (?,?,?,?,?)", TITLES)
            db.executemany("INSERT INTO genres VALUES (?,?,?)", [
                (1, "Sci-Fi", "sci-fi"), (2, "Fantasy", "fantasy"),
                (3, "Crime", "crime"), (4, "Drama", "drama")])
            db.executemany("INSERT INTO title_genre VALUES (?,?)", [
                (1, 1), (2, 2), (3, 1), (3, 2), (4, 3), (5, 2), (6, 1),
                (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 4),
                (13, 3), (14, 1),
            ])
            db.executemany("INSERT INTO watchlist_items VALUES (?,?,?,?)", [
                (100 + title_id, 1, title_id, "2025-01-01 00:00:00") for title_id in range(1, 6)
            ] + [
                (200 + title_id, 2, title_id, "2025-01-01 00:00:00") for title_id in range(7, 13)
            ] + [(301, 4, 1, "2025-01-01 00:00:00"), (302, 4, 13, "2025-01-01 00:00:00")])
            db.executemany("INSERT INTO user_ratings VALUES (?,?,?,?,?)", [
                (501, 2, 7, 6, "2025-02-03 04:05:06"),
                (502, 2, 9, 8, "2025-02-04 04:05:06"),
                (503, 2, 10, 7, "2025-02-05 04:05:06"),
                (504, 1, 7, 3, "2025-02-06 04:05:06"),
            ])
            db.execute("INSERT INTO reviews VALUES (601,14,3,7,'Existing synthetic review',"
                       "'An existing body.',4,'2025-03-01 00:00:00',1)")
            db.execute("INSERT INTO news_items VALUES (1,'Synthetic bulletin','Keep unchanged',"
                       "'Fixture','2025-01-01','Synthetic','')")
        self.reset_after()

    def reset_after(self):
        shutil.copyfile(self.run_dir / "before.db", self.run_dir / "after.db")

    def change(self, sql, parameters=(), both=False):
        for filename in (("before.db", "after.db") if both else ("after.db",)):
            with sqlite3.connect(self.run_dir / filename) as db:
                db.execute(sql, parameters)

    def apply_expected_delta(self, number):
        if number == 15:
            self.change("DELETE FROM watchlist_items WHERE id=101")
        elif number == 16:
            self.change("UPDATE user_ratings SET rating=8 WHERE id=501")
        elif number == 17:
            self.change("INSERT INTO reviews VALUES (602,14,3,10,?,?,?,?,?)", (
                "Brilliant sci-fi epic", "A nonempty synthetic review body.",
                0, "2026-09-08 09:10:11", 0))

    def step(self, path, action="goto", params=None, after=None, native=False):
        step = {"url": self.origin + path, "action": action, "params": params or {},
                "action_result": {"success": None if native else True, "error": None}}
        if not native:
            step["status"] = "completed"
        if after is not None:
            step["url_after"] = self.origin + after
        return step

    def login_steps(self, user_id, enter=False):
        return [
            self.step("/login"),
            self.step("/login", "fill", {"selector": "input[name=email]", "value": EMAILS[user_id]}),
            self.step("/login", "fill", {"selector": "input[name=password]", "value": "TestPass123!"}),
            self.step("/login", "press" if enter else "click",
                      {"selector": "input[name=password]", "key": "Enter"} if enter
                      else {"selector": "button[type=submit]", "text": "Sign in"}, after="/"),
            self.step("/"),
        ]

    def task_steps(self, number, *, title_remove=False, native=False, user_id=None,
                   enter_login=False, review_sort="helpful", review_entry="title"):
        steps = self.login_steps(USERS[number] if user_id is None else user_id, enter_login)
        if number == 15:
            steps.append(self.step("/list/watchlist"))
            source = f"/title/{ORBIT}" if title_remove else "/list/watchlist"
            if title_remove:
                steps.append(self.step(source))
            params = {"index": 3} if native else {
                "selector": f'form[action="/title/{ORBIT}/watchlist"] button', "text": "Remove"}
            steps.append(self.step(source, "click", params, after=source, native=native))
            steps.append(self.step(source))
        elif number == 16:
            source = f"/title/{CRIME}"
            steps += [self.step("/list/watchlist"), self.step(source),
                      self.step(source, "fill", {"selector": "input[name=rating]", "value": "8"})]
            params = {"index": 3} if native else {
                "selector": f'form[action="{source}/rate"] button', "text": "Rate"}
            steps.append(self.step(source, "click", params, after=source, native=native))
            steps.append(self.step("/list/ratings"))
        elif number == 17:
            title = f"/title/{INTERSTELLAR}"
            form = title + "/review"
            if review_entry == "title":
                steps.append(self.step(title))
            elif review_entry == "reviews":
                steps.append(self.step(title + "/reviews"))
            steps += [self.step(form),
                      self.step(form, "fill", {"selector": "input[name=headline]", "value": "Brilliant sci-fi epic"}),
                      self.step(form, "fill", {"selector": "textarea[name=body]", "value": "A nonempty synthetic review body."}),
                      self.step(form, "fill", {"selector": "input[name=rating]", "value": "10"})]
            params = {"index": 3} if native else {"selector": "button[type=submit]", "text": "Submit review"}
            destination = title + "/reviews?sort=" + review_sort
            steps.append(self.step(form, "click", params, after=destination, native=native))
            steps.append(self.step(destination))
        return steps

    def check(self, number, answer=None, steps=None):
        task_id = f"IMDb--{number}"
        trajectory = {"task_id": task_id, "task": TASKS[task_id]["ques"],
                      "start_url": self.origin + "/", "fixture_kind": "synthetic",
                      "final_answer": ANSWERS[number] if answer is None else answer,
                      "steps": self.task_steps(number) if steps is None else steps}
        (self.run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        with RunEvidence(self.run_dir, task_id, expected_ques=TASKS[task_id]["ques"]) as run:
            return state_tasks.check_state_task(number, run)

    def assert_accepts(self, number, answer=None, steps=None):
        self.assertIsInstance(self.check(number, answer, steps), list)

    def assert_rejects(self, number, answer=None, steps=None):
        with self.assertRaises(VerificationError):
            self.check(number, answer, steps)

    def test_task15_removes_earliest_qualifying_tv_with_alphabetical_tie_break(self):
        self.apply_expected_delta(15)
        self.assert_accepts(15)

    def test_task15_target_title_removal_and_confirmation_are_valid(self):
        self.apply_expected_delta(15)
        self.assert_accepts(15, steps=self.task_steps(15, title_remove=True))

    def test_task15_either_qualifying_genre_is_sufficient(self):
        self.change("UPDATE title_genre SET genre_id=2 WHERE title_id=1", both=True)
        self.apply_expected_delta(15)
        self.assert_accepts(15, ANSWERS[15].replace("Sci-Fi", "Fantasy"))

    def test_task15_reports_both_qualifying_genres_when_both_present(self):
        self.change("INSERT INTO title_genre VALUES (1,2)", both=True)
        self.apply_expected_delta(15)
        self.assert_accepts(15, ANSWERS[15].replace("Sci-Fi", "Sci-Fi and Fantasy"))
        self.assert_rejects(15)

    def test_task15_wrong_tie_choice_type_or_genre_is_rejected(self):
        for item_id in (102, 103, 104, 105, 301):
            with self.subTest(item_id=item_id):
                self.reset_after()
                self.change("DELETE FROM watchlist_items WHERE id=?", (item_id,))
                self.assert_rejects(15)

    def test_task15_removing_an_additional_watchlist_item_is_rejected(self):
        self.apply_expected_delta(15)
        self.change("DELETE FROM watchlist_items WHERE id=102")
        self.assert_rejects(15)

    def test_task16_updates_only_existing_target_rating(self):
        self.apply_expected_delta(16)
        self.assert_accepts(16)

    def test_task16_unrated_target_gets_one_new_rating(self):
        self.change("DELETE FROM user_ratings WHERE id=501", both=True)
        self.change("INSERT INTO user_ratings VALUES (550,2,7,8,'2026-09-08 09:10:11')")
        self.assert_accepts(16)

    def test_task16_null_personal_rating_is_eligible(self):
        self.change("UPDATE user_ratings SET rating=NULL WHERE id=501", both=True)
        self.apply_expected_delta(16)
        self.assert_accepts(16)

    def test_task16_existing_rating_keeps_id_and_created_at(self):
        for sql in ("UPDATE user_ratings SET rating=8, id=550 WHERE id=501",
                    "UPDATE user_ratings SET rating=8, created_at='2026-09-08 09:10:11' WHERE id=501"):
            with self.subTest(sql=sql):
                self.reset_after()
                self.change(sql)
                self.assert_rejects(16)

    def test_task16_newer_but_already_eight_and_nonmovie_or_nongenre_are_excluded(self):
        for title_id in (8, 9, 10, 11, 12, 13):
            with self.subTest(title_id=title_id):
                self.reset_after()
                self.change("DELETE FROM user_ratings WHERE user_id=2 AND title_id=?", (title_id,))
                self.change("INSERT INTO user_ratings VALUES (550,2,?,8,'2026-09-08 09:10:11')", (title_id,))
                self.assert_rejects(16)

    def test_task16_another_users_rating_or_global_rating_cannot_change(self):
        for sql in ("UPDATE user_ratings SET rating=8 WHERE id=504",
                    "UPDATE titles SET rating_avg=8 WHERE id=7"):
            with self.subTest(sql=sql):
                self.reset_after()
                self.apply_expected_delta(16)
                self.change(sql)
                self.assert_rejects(16)

    def test_task17_creates_exactly_one_review_without_personal_rating_write(self):
        self.apply_expected_delta(17)
        self.assert_accepts(17)

    def test_task17_any_review_sort_and_direct_or_reviews_entry_are_valid(self):
        self.apply_expected_delta(17)
        for order in ("helpful", "recent", "rating"):
            for entry in ("title", "direct", "reviews"):
                with self.subTest(order=order, entry=entry):
                    self.assert_accepts(17, steps=self.task_steps(17, review_sort=order, review_entry=entry))

    def test_task17_created_review_fields_must_match(self):
        changes = [("user_id", 4), ("title_id", 7), ("headline", "brilliant sci-fi epic"),
                   ("headline", "Brilliant sci-fi epic!"), ("rating", 9),
                   ("body", " \n\t"), ("helpful_count", 1), ("is_seed", 1)]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                self.reset_after()
                self.apply_expected_delta(17)
                self.change(f"UPDATE reviews SET {field}=? WHERE id=602", (value,))
                self.assert_rejects(17)

    def test_task17_new_review_body_can_be_any_nonempty_text(self):
        self.apply_expected_delta(17)
        self.change("UPDATE reviews SET body='A different, nonempty review.' WHERE id=602")
        steps = self.task_steps(17)
        for step in steps:
            if step.get("params", {}).get("selector") == "textarea[name=body]":
                step["params"]["value"] = "A different, nonempty review."
        self.assert_accepts(17, steps=steps)

    def test_task17_extra_review_or_rating_write_is_rejected(self):
        for sql in (
            "INSERT INTO reviews SELECT 603,title_id,user_id,rating,headline,body,helpful_count,created_at,is_seed FROM reviews WHERE id=602",
            "INSERT INTO user_ratings VALUES (550,3,14,10,'2026-09-08 09:10:11')",
            "UPDATE reviews SET body='Changed old review' WHERE id=601",
        ):
            with self.subTest(sql=sql):
                self.reset_after()
                self.apply_expected_delta(17)
                self.change(sql)
                self.assert_rejects(17)

    def test_noop_is_not_success_even_if_answer_and_steps_claim_success(self):
        for number in USERS:
            with self.subTest(number=number):
                self.assert_rejects(number)

    def test_each_task_rejects_changes_to_unrelated_business_tables(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                self.change("UPDATE news_items SET headline='Unexpected mutation' WHERE id=1")
                self.assert_rejects(number)

    def test_correct_delta_requires_login_with_the_requested_account(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                self.assert_rejects(number, steps=self.task_steps(number, user_id=4))
                self.assert_rejects(number, steps=self.task_steps(number)[5:])

    def test_enter_can_submit_login(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                self.assert_accepts(number, steps=self.task_steps(number, enter_login=True))

    def test_native_index_click_with_unknown_success_uses_later_page_and_delta(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number, native=True)
                for step in steps:
                    step.pop("status", None)
                    step["action_result"]["success"] = None
                self.assert_accepts(number, steps=steps)

    def test_explicit_failed_mutation_is_not_rescued_by_a_plausible_delta(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                steps[-2]["status"] = "failed"
                steps[-2]["action_result"] = {"success": True, "error": "Synthetic click failed"}
                self.assert_rejects(number, steps=steps)

    def test_unknown_after_url_alone_does_not_confirm_mutation(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number, native=True)[:-1]
                self.assert_rejects(number, steps=steps)

    def test_explicit_success_after_url_can_confirm_the_review(self):
        self.apply_expected_delta(17)
        self.assert_accepts(17, steps=self.task_steps(17)[:-1])

    def test_pure_navigation_does_not_prove_a_mutation_action(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                for step in steps[5:]:
                    step["action"] = "goto"
                    step["params"] = {}
                self.assert_rejects(number, steps=steps)

    def test_foreign_login_and_mutation_urls_do_not_count(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                for step in steps:
                    for key in ("url", "url_after"):
                        if key in step:
                            step[key] = step[key].replace(self.origin, "http://foreign.example")
                self.assert_rejects(number, steps=steps)

    def test_required_candidate_and_confirmation_pages_cannot_be_omitted(self):
        self.apply_expected_delta(15)
        # Using a title removal control still requires the initial Watchlist candidate set.
        steps = [step for step in self.task_steps(15, title_remove=True)
                 if not step["url"].endswith("/list/watchlist")]
        self.assert_rejects(15, steps=steps)
        self.reset_after()
        self.apply_expected_delta(16)
        steps = [step for step in self.task_steps(16) if not step["url"].endswith("/list/watchlist")]
        self.assert_rejects(16, steps=steps)
        self.assert_rejects(16, steps=self.task_steps(16)[:-1])
        self.reset_after()
        self.apply_expected_delta(17)
        steps = [step for step in self.task_steps(17) if not step["url"].endswith("/review")]
        self.assert_rejects(17, steps=steps)

    def test_explicit_wrong_target_controls_are_rejected(self):
        for number in (15, 16):
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                steps[-2]["params"]["selector"] = 'form[action="/title/tt9100002/watchlist"] button'
                self.assert_rejects(number, steps=steps)

    def test_explicit_conflicting_form_values_are_rejected(self):
        for number, selector, wrong_value in (
            (16, "input[name=rating]", "7"),
            (17, "input[name=rating]", "9"),
            (17, "input[name=headline]", "A different headline"),
        ):
            with self.subTest(number=number, selector=selector):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                for step in steps:
                    if step["params"].get("selector") == selector:
                        step["params"]["value"] = wrong_value
                self.assert_rejects(number, steps=steps)

    def test_answers_must_report_the_selected_target_and_result(self):
        wrong = {15: "Beta Realm (1990), Fantasy, was removed from Bob's Watchlist.",
                 16: "Alpha Crime (2020) is now rated 7/10 in My ratings.",
                 17: "Submitted A different headline for Interstellar with rating 10/10."}
        for number, answer in wrong.items():
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                self.assert_rejects(number, answer)
                self.assert_rejects(number, steps=[])

    def test_private_confirmation_cannot_belong_to_a_different_account(self):
        for number in (15, 16):
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                confirmation = steps.pop()
                steps[-1].pop("url_after", None)
                steps.extend(self.login_steps(4))
                steps.append(confirmation)
                self.assert_rejects(number, steps=steps)

    def test_watchlist_candidate_page_must_belong_to_the_requested_account(self):
        for number in (15, 16):
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                wrong_watchlist = self.login_steps(4) + [self.step("/list/watchlist")]
                rest = [step for step in self.task_steps(number, title_remove=True)
                        if not step["url"].endswith("/list/watchlist")]
                self.assert_rejects(number, steps=wrong_watchlist + rest)

    def test_personal_and_review_ratings_are_distinct_from_imdb_context(self):
        self.apply_expected_delta(16)
        self.assert_accepts(16, "Alpha Crime (2020): personal rating 8/10; IMDb rating 7.0/10. Confirmed in My ratings.")
        self.assert_rejects(16, "Alpha Crime (2020): personal rating 7/10; IMDb rating 8/10. Confirmed in My ratings.")
        self.reset_after()
        self.apply_expected_delta(17)
        self.assert_accepts(17, "Interstellar: my review rating is 10/10; IMDb rating 7.0/10. The review is visible.")
        self.assert_rejects(17, "Interstellar: my review rating is 9/10; IMDb rating 10/10. The review is visible.")

    def test_review_confirmation_can_be_concise_but_cannot_claim_a_wrong_headline(self):
        self.apply_expected_delta(17)
        self.assert_accepts(17, "Confirmed: the new review is visible on the user reviews page.")
        self.assert_rejects(17, 'Interstellar review "Wrong headline" is now visible.')
        self.assert_rejects(17, 'Interstellar: headline Wrong headline. The new review is visible.')
        self.assert_accepts(17, 'Interstellar: headline Brilliant sci-fi epic; the new review is visible.')

    def test_explicit_cancel_text_does_not_count_as_a_submission(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number)
                steps[-2]["params"] = {"text": "Cancel"}
                self.assert_rejects(number, steps=steps)

    def test_abandoned_form_inputs_do_not_override_a_reopened_native_form(self):
        self.apply_expected_delta(16)
        source = f"/title/{CRIME}"
        steps = self.task_steps(16, native=True)
        position = next(index for index, step in enumerate(steps) if step["params"].get("selector") == "input[name=rating]")
        steps[position:position] = [self.step(source, "fill", {"selector": "input[name=rating]", "value": "7"}),
                                   self.step("/list/watchlist"), self.step(source)]
        corrected = next(step for step in reversed(steps) if step["action"] == "fill")
        corrected["params"] = {"index": 7, "value": "8"}
        self.assert_accepts(16, steps=steps)

    def test_last_corrected_form_value_is_used(self):
        self.apply_expected_delta(16)
        steps = self.task_steps(16)
        wrong = self.step(f"/title/{CRIME}", "fill", {"selector": "input[name=rating]", "value": "7"})
        position = next(index for index, step in enumerate(steps) if step["params"].get("selector") == "input[name=rating]")
        steps.insert(position, wrong)
        self.assert_accepts(16, steps=steps)

    def test_native_unknown_login_and_enter_submission_are_supported(self):
        for number in USERS:
            with self.subTest(number=number):
                self.reset_after()
                self.apply_expected_delta(number)
                steps = self.task_steps(number, native=True)
                for step in steps:
                    step.pop("status", None)
                    step["action_result"] = {"success": None, "error": None}
                steps[-2]["action"] = "press_key"
                steps[-2]["params"] = {"key": "Enter"}
                self.assert_accepts(number, steps=steps)

    def test_get_and_head_logout_405_observations_preserve_login(self):
        self.apply_expected_delta(16)
        for method in ("GET", "HEAD"):
            with self.subTest(method=method):
                steps = self.task_steps(16)
                rejected = self.step("/logout", "goto", {"method": method}, after="/logout")
                rejected["action_result"]["status_code"] = 405
                steps[5:5] = [rejected, self.step("/logout", "observe"), self.step("/")]
                self.assert_accepts(16, steps=steps)

    def test_obsolete_logout_get_link_does_not_clear_login(self):
        self.apply_expected_delta(16)
        steps = self.task_steps(16)
        rejected = self.step("/", "click", {"selector": 'a[href="/logout"]',
                                            "text": "Sign out", "method": "GET"}, after="/logout")
        rejected["action_result"]["status_code"] = 405
        steps[5:5] = [rejected, self.step("/logout", "observe"), self.step("/")]
        self.assert_accepts(16, steps=steps)

    def test_post_logout_button_or_enter_clears_the_previous_login(self):
        self.apply_expected_delta(16)
        for action, selector in (
            ("click", 'form[action="/logout"][method="post"] button'),
            ("press_key", 'form[action="/logout"][method="post"] button'),
            ("click", "button.nav-link"),
        ):
            with self.subTest(action=action, selector=selector):
                steps = self.task_steps(16)
                params = {"selector": selector,
                          "method": "POST", "text": "Sign out"}
                if action == "press_key":
                    params["key"] = "Enter"
                steps[5:5] = [self.step("/", action, params, after="/"), self.step("/")]
                self.assert_rejects(16, steps=steps)

    def test_native_unknown_logout_needs_a_later_local_observation(self):
        task_id = "IMDb--16"
        steps = self.login_steps(2) + [self.step("/", "click", {"text": "Sign out"}, native=True)]
        for observed in (False, True):
            with self.subTest(observed=observed):
                recorded = steps + ([self.step("/")] if observed else [])
                trajectory = {"task_id": task_id, "task": TASKS[task_id]["ques"],
                              "start_url": self.origin + "/", "steps": recorded}
                (self.run_dir / "trajectory.json").write_text(json.dumps(trajectory))
                with RunEvidence(self.run_dir, task_id) as run:
                    self.assertEqual(state_tasks._login_before(run, len(recorded), EMAILS[2]), not observed)


if __name__ == "__main__":
    unittest.main()
