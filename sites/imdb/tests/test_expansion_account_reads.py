"""Synthetic account-read fixtures; none of these are browser executions."""

import hashlib
import json
import sqlite3
import unittest

import test_read_tasks as catalog
from expansion_account_reads import check_account_read_task
from verify_lib import RunEvidence, VerificationError


PASSWORD = "TestPass123!"
HASH = "pbkdf2:sha256:1000$salt$" + hashlib.pbkdf2_hmac(
    "sha256", PASSWORD.encode(), b"salt", 1000).hex()

ANSWER21 = """| Account | Film | Personal rating | Director | Runtime |
|---|---|---|---|---|
| Alice | The Godfather | 9/10 | Francis Ford Coppola | 175 minutes |
| Alice | Inception | 10/10 | Christopher Nolan | 148 minutes |
| Bob | The Dark Knight | 10/10 | Christopher Nolan | 152 minutes |
| Bob | Synthetic Cutoff Echo | 9/10 | Synthetic Director | 100 minutes |
"""
ANSWER22 = """The Dark Knight (2008) — repeated headline: Same words.

| Author | Review score | Review date | Helpful count |
|---|---|---|---|
| Alice Johnson | 9/10 | 2020-02-03 | 42 |
| DustBowlPilot | 7/10 | 2021-03-04 | 18 |
"""


class SyntheticAccountReadTests(unittest.TestCase):
    def setUp(self):
        self.fixture = catalog.SyntheticReadTaskTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.directory = self.fixture.run_dir
        self.origin = self.fixture.origin
        self.change("UPDATE users SET email='alice.j@test.com',name='Alice Johnson',password_hash=? WHERE id=1", (HASH,))
        self.change("UPDATE users SET email='bob.c@test.com',name='Bob Carter',password_hash=? WHERE id=2", (HASH,))
        self.change("INSERT INTO users VALUES (3,'pilot@example.test','DustBowlPilot',?,'2020-01-01')", (HASH,))
        for row in [(1, 1, 9), (1, 2, 9), (1, 4, 10), (1, 5, 7),
                    (2, 3, 10), (2, 2, 8), (2, 5, 9), (2, 6, 9)]:
            self.change("INSERT INTO user_ratings(user_id,title_id,rating,created_at) VALUES (?,?,?,'2024-01-01')", row)
        for row in [(1, 1), (1, 3), (1, 6), (2, 1), (2, 5), (2, 4)]:
            self.change("INSERT INTO watchlist_items(user_id,title_id,added_at) VALUES (?,?,'2024-01-01')", row)
        for row in [(3, 1, 9, "Same words", 42, "2020-02-03"),
                    (3, 3, 7, "Same words", 18, "2021-03-04"),
                    (1, 1, 10, "Different first", 11, "2020-01-01"),
                    (1, 3, 8, "Different second", 13, "2022-01-01")]:
            self.change("INSERT INTO reviews(title_id,user_id,rating,headline,helpful_count,created_at,body,is_seed) "
                        "VALUES (?,?,?,?,?,?,'Synthetic review',1)", row)

    def change(self, sql, values=(), after_only=False):
        names = ("after.db",) if after_only else ("before.db", "after.db")
        for name in names:
            with sqlite3.connect(self.directory / name) as db:
                db.execute(sql, values)

    def step(self, path, action="observe", params=None, after=None, success=True):
        step = {"url": self.origin + path, "action": action, "params": params or {},
                "status": "completed", "action_result": {"success": success}}
        if after is not None:
            step["url_after"] = self.origin + after
        return step

    def account_steps(self, name):
        email = {"alice": "alice.j@test.com", "bob": "bob.c@test.com"}[name]
        return [self.step("/login", "fill", {"label": "Email", "value": email}),
                self.step("/login", "fill", {"label": "Password", "value": PASSWORD}),
                self.step("/login", "click", {"role": "button", "name": "Sign in"}, "/"),
                self.step("/list/ratings"), self.step("/list/watchlist")]

    def steps(self, number):
        steps = self.account_steps("alice")
        if number == 21:
            steps += [self.step("/list/watchlist", "click", {"role": "button", "name": "Sign out", "method": "POST"}, "/")]
            steps += self.account_steps("bob")
            steps += [self.step("/title/" + identifier)
                      for identifier in (catalog.GOD, catalog.INCEPTION, catalog.DARK, catalog.ECHO)]
        else:
            steps += [self.step("/title/" + catalog.DARK + "/reviews?sort=recent")]
        return steps

    def check(self, number, answer=None, steps=None):
        task_id = f"IMDb--{number}"
        question = catalog.TASKS[task_id]["ques"]
        row = {"task_id": task_id, "task": question, "start_url": self.origin + "/",
               "steps": self.steps(number) if steps is None else steps,
               "final_answer": {21: ANSWER21, 22: ANSWER22}[number] if answer is None else answer,
               "fixture_kind": "synthetic"}
        (self.directory / "trajectory.json").write_text(json.dumps(row))
        with RunEvidence(self.directory, task_id, question) as run:
            return check_account_read_task(number, run)

    def rejects(self, number, answer=None, steps=None):
        with self.assertRaises(VerificationError):
            self.check(number, answer, steps)

    def test_complete_attributed_account_table_needs_no_unrequested_years(self):
        self.check(21)

    def test_account_heading_sections_with_prose_are_valid(self):
        self.check(21, """Alice

The Godfather: personal rating 9/10; directed by Francis Ford Coppola; runtime 175 minutes.
Inception: personal rating 10/10; directed by Christopher Nolan; runtime 148 minutes.

Bob

The Dark Knight: personal rating 10/10; directed by Christopher Nolan; runtime 152 minutes.
Synthetic Cutoff Echo: personal rating 9/10; directed by Synthetic Director; runtime 100 minutes.
""")

    def test_both_source_orders_and_fullcredits_are_valid(self):
        steps = self.account_steps("bob")
        steps += [self.step("/list/watchlist", "click", {"role": "button", "name": "Sign out", "method": "POST"}, "/")]
        steps += list(self.account_steps("alice"))
        steps += [self.step("/title/" + identifier + "/fullcredits")
                  for identifier in (catalog.ECHO, catalog.DARK, catalog.INCEPTION, catalog.GOD)]
        self.check(21, steps=steps)

    def test_wrong_owner_partial_result_global_score_and_swapped_runtime_fail(self):
        bad = [ANSWER21.replace("| Alice | Inception", "| Bob | Inception"),
               ANSWER21.replace("| Bob | Synthetic Cutoff Echo | 9/10 | Synthetic Director | 100 minutes |", ""),
               ANSWER21.replace("9/10 | Francis", "9.2/10 | Francis"),
               ANSWER21.replace("175 minutes", "148 minutes"),
               ANSWER21.replace("Francis Ford Coppola", "Christopher Nolan"),
               ANSWER21.replace("10/10 | Christopher Nolan | 152", "8/10 | Christopher Nolan | 152")]
        for answer in bad:
            with self.subTest(answer=answer):
                self.rejects(21, answer)

    def test_eligible_set_cannot_include_an_existing_watchlist_item(self):
        extra = "| Alice | The Shawshank Redemption | 9/10 | Frank Darabont | 142 minutes |\n"
        self.rejects(21, ANSWER21 + extra)

    def test_missing_source_list_or_wrong_authentication_fails(self):
        for number in (21, 22):
            with self.subTest(number=number):
                steps = [s for s in self.steps(number) if not s["url"].endswith("/list/ratings")]
                self.rejects(number, steps=steps)
                steps = self.steps(number)
                steps[1]["params"]["value"] = "incorrect-password"
                self.rejects(number, steps=steps)
                steps = self.steps(number)
                steps[2]["action_result"]["success"] = False
                self.rejects(number, steps=steps)

    def test_supplied_password_redaction_uses_snapshot_hash_and_successful_login(self):
        for number in (21, 22):
            with self.subTest(number=number):
                steps = self.steps(number)
                for step in steps:
                    if step["params"].get("label") == "Password":
                        step["params"]["value"] = "[SUPPLIED PASSWORD]"
                self.check(number, steps=steps)

    def test_review_table_beneath_movie_heading_is_valid(self):
        self.check(22)

    def test_review_prose_and_written_dates_are_valid(self):
        self.check(22, """The Dark Knight (2008), repeated headline: Same words.
Alice Johnson: review score 9/10; February 3, 2020; 42 found this helpful.
DustBowlPilot: review score 7/10; 4 March 2021; 18 helpful.
""")

    def test_review_summary_intro_is_not_misread_as_an_unknown_author(self):
        self.check(22, "Alice's deduplicated Watchlist union My ratings contains six movies. "
                   "Exactly one repeated-headline group appears:\n\n" + ANSWER22)

    def test_title_column_in_review_table_is_valid(self):
        self.check(22, """Repeated headline: Same words.
| Film | Year | Author | Review score | Review date | Helpful count |
|---|---|---|---|---|---|
| The Dark Knight | 2008 | Alice Johnson | 9/10 | 2020-02-03 | 42 |
| The Dark Knight | 2008 | DustBowlPilot | 7/10 | 2021-03-04 | 18 |
""")

    def test_any_review_sort_is_valid_but_details_only_lack_review_dates(self):
        for sort in ("helpful", "rating", "recent"):
            steps = self.account_steps("alice") + [self.step("/title/" + catalog.DARK + "/reviews?sort=" + sort)]
            self.check(22, steps=steps)
        self.rejects(22, steps=self.account_steps("alice") + [self.step("/title/" + catalog.DARK)])

    def test_swapped_author_dates_scores_and_helpful_counts_fail(self):
        changes = [("9/10", "7/10"), ("2020-02-03", "2021-03-04"),
                   ("| 42 |", "| 18 |"), ("Alice Johnson", "Bob Carter"),
                   ("Same words", "Different first"), ("(2008)", "(2007)")]
        for before, after in changes:
            with self.subTest(field=before):
                self.rejects(22, ANSWER22.replace(before, after))

    def test_omitted_review_row_or_field_fails(self):
        for part in ("| DustBowlPilot | 7/10 | 2021-03-04 | 18 |", "9/10", "2020-02-03", "42"):
            with self.subTest(part=part):
                self.rejects(22, ANSWER22.replace(part, ""))

    def test_extra_review_author_rows_fail(self):
        for author in ("Bob Carter", "An Invented Author"):
            self.rejects(22, ANSWER22 + f"| {author} | 7/10 | 2021-03-04 | 18 |\n")

    def test_equal_headline_on_another_movie_does_not_join_group(self):
        self.change("UPDATE reviews SET headline='Same words' WHERE title_id=1 AND user_id=1")
        self.check(22)

    def test_same_author_repetition_without_distinct_authors_is_not_a_group(self):
        self.change("UPDATE reviews SET user_id=1 WHERE title_id=3")
        self.rejects(22)

    def test_closed_21_extra_tv_outside_union_and_unknown_results_fail(self):
        for title in ("Synthetic Crime Series", "Synthetic Writer Only Feature", "Invented Extra Film"):
            for extra in (f"Alice: Also include {title} as a qualifying movie.",
                          f"| Alice | {title} | 10/10 | Christopher Nolan | 148 minutes |"):
                with self.subTest(extra=extra):
                    self.rejects(21, ANSWER21 + extra)
        self.check(21, ANSWER21 + "Alice: Synthetic Crime Series is excluded because it is a TV series.")

    def test_closed_21_equivalent_runtime_units_and_contradictions(self):
        answer = ANSWER21
        for minutes, hours in ((175, "2h 55m"), (148, "2h 28m"), (152, "2 hours 32 minutes"), (100, "1h 40m")):
            answer = answer.replace(f"{minutes} minutes", hours)
        self.check(21, answer)
        self.rejects(21, answer.replace("2h 55m", "2h 54m"))
        self.rejects(21, answer.replace("2h 55m", "2h 55m (174 minutes)"))

    def test_closed_scores_accept_rated_out_of_ten_and_global_context(self):
        answer = ANSWER21.replace("9/10", "rated 9 out of 10").replace("10/10", "rated 10 out of 10")
        self.check(21, answer)
        self.check(21, ANSWER21.replace("9/10 | Francis", "9/10 (IMDb rating is 9.2/10) | Francis"))
        self.rejects(21, ANSWER21.replace("9/10 | Francis", "8/10 (IMDb rating is 9/10) | Francis"))
        self.check(22, ANSWER22.replace("9/10", "rated 9 out of 10"))
        self.rejects(22, ANSWER22.replace("9/10", "rated 8 out of 10"))

    def test_closed_22_headline_exactness_and_extra_group(self):
        self.rejects(22, ANSWER22.replace("Same words", "Same words with extras"))
        self.rejects(22, ANSWER22 + ANSWER22.replace("Same words", "Invented group"))
        self.check(22, ANSWER22.replace("Same words.", '\"Same words\".'))

    def add_review(self, score=8, headline="Other words", user=1, date="2022-04-05", helpful=12):
        self.change("INSERT INTO reviews(title_id,user_id,rating,headline,helpful_count,created_at,body,is_seed) "
                    "VALUES (3,?,?,?,?,?,'Synthetic repeated review',1)",
                    (user, score, headline, helpful, date))

    def test_closed_22_same_movie_multiple_groups_are_separate(self):
        self.add_review()
        self.add_review(6, user=3, date="2023-05-06", helpful=14)
        other = ANSWER22.replace("Same words", "Other words").replace("9/10", "8/10").replace("7/10", "6/10").replace("2020-02-03", "2022-04-05").replace("2021-03-04", "2023-05-06").replace("42", "12").replace("18", "14")
        self.check(22, ANSWER22 + "\n" + other)
        self.rejects(22, ANSWER22)
        self.rejects(22, ANSWER22 + "\n" + other.replace("Other words", "Same words"))

    def test_closed_22_repeated_author_reviews_require_row_multiplicity(self):
        self.add_review(headline="Same words")
        extra = "| Alice Johnson | 8/10 | 2022-04-05 | 12 |\n"
        self.check(22, ANSWER22 + extra)
        self.rejects(22, ANSWER22)
        self.rejects(22, ANSWER22 + extra.replace("8/10", "9/10"))
        self.add_review(9, "Same words", date="2020-02-03", helpful=42)
        self.rejects(22, ANSWER22 + extra)
        self.check(22, ANSWER22 + extra + "| Alice Johnson | 9/10 | 2020-02-03 | 42 |\n")

    def test_closed_22_extra_prose_author_and_explicit_exclusion(self):
        for author in ("Bob Carter", "An Invented Author"):
            self.rejects(22, ANSWER22 + f"Additional matching author: {author}; review score 7/10; 2021-03-04; helpful count 18.")
        self.check(22, ANSWER22 + "Bob Carter is excluded; he is not in this matching group.")

    def test_closed_22_unambiguous_author_and_title_aliases(self):
        self.check(22, ANSWER22.replace("Alice Johnson", "Alice").replace("The Dark Knight", "Dark Knight"))
        self.rejects(22, ANSWER22.replace("Alice Johnson", "Bob"))
        self.change("INSERT INTO users VALUES (4,'other@example.test','Alice Smith',?,'2020-01-01')", (HASH,))
        self.rejects(22, ANSWER22.replace("Alice Johnson", "Alice"))
        self.check(22, ANSWER22)

    def test_closed_review_multiline_and_single_paragraph_records(self):
        heading = "The Dark Knight (2008); repeated headline: Same words.\n"
        rows = ["Alice Johnson: review score 9/10; review date 2020-02-03; helpful count 42.",
                "DustBowlPilot: review score 7/10; review date 2021-03-04; helpful count 18."]
        self.check(22, heading + " ".join(rows))
        multiline = heading + "Alice Johnson\nReview score: 9/10\nReview date: 2020-02-03\nHelpful count: 42\nDustBowlPilot\nReview score: 7/10\nReview date: 2021-03-04\nHelpful count: 18"
        self.check(22, multiline)
        self.rejects(22, multiline.replace("Review score: 7/10", "Review score: 9/10"))
        self.rejects(22, multiline + "\nAn Invented Author: review score 7/10; 2021-03-04; helpful count 18.")

    def test_closed_review_scope_in_headings_and_table_columns(self):
        self.check(22, ANSWER22.replace("repeated headline: Same words.", '\"Same words\".'))
        self.check(22, "The Dark Knight (2008), repeated headline: Same words.\n" +
                   "| Film | Author | Review score | Review date | Helpful count |\n|---|---|---|---|---|\n" +
                   "| The Dark Knight | Alice | 9/10 | 2020-02-03 | 42 |\n" +
                   "| The Dark Knight | DustBowlPilot | 7/10 | 2021-03-04 | 18 |")
        self.check(22, "| Film | Year | Headline | Author | Review score | Review date | Helpful count |\n|---|---|---|---|---|---|---|\n" +
                   "| The Dark Knight | 2008 | Same words | Alice | 9/10 | 2020-02-03 | 42 |\n" +
                   "| The Dark Knight | 2008 | Same words | DustBowlPilot | 7/10 | 2021-03-04 | 18 |")

    def test_closed_bilingual_fields_scores_dates_and_runtime(self):
        answer21 = ANSWER21.replace("Account", "账号").replace("Film", "电影").replace("Personal rating", "个人评分").replace("| Director |", "| 导演 |").replace("Runtime", "片长").replace("minutes", "分钟")
        self.check(21, answer21)
        self.check(21, "Alice账号：\nThe Godfather：个人评分9分，导演Coppola，片长2小时55分钟。\nInception：个人评分10分，导演Nolan，片长148分钟。\nBob账号：\nThe Dark Knight：个人评分10分，导演Nolan，片长152分钟。\nSynthetic Cutoff Echo：个人评分9分，导演Synthetic Director，片长100分钟。")
        answer22 = ANSWER22.replace("repeated headline:", "重复标题：").replace("Author", "作者").replace("Review score", "影评评分").replace("Review date", "评论日期").replace("Helpful count", "有用数")
        self.check(22, answer22)
        self.check(22, "The Dark Knight (2008)，重复标题：Same words。\nAlice：影评评分9分（满分10分）；日期2020年2月3日；有用数42。\nDustBowlPilot：影评评分7分（满分10分）；日期2021年3月4日；有用数18。")
        self.rejects(22, answer22.replace("9/10", "8/10"))

    def test_noop_answer_only_foreign_pages_and_extra_business_changes_fail(self):
        for number in (21, 22):
            with self.subTest(number=number):
                self.rejects(number, answer="", steps=[self.step("/")])
                self.rejects(number, steps=[])
                steps = self.steps(number)
                for step in steps:
                    step["url"] = step["url"].replace(self.origin, "https://www.imdb.com")
                    if "url_after" in step:
                        step["url_after"] = step["url_after"].replace(self.origin, "https://www.imdb.com")
                self.rejects(number, steps=steps)
        self.change("UPDATE reviews SET helpful_count=helpful_count+1", after_only=True)
        self.rejects(21)
        self.rejects(22)


if __name__ == "__main__":
    unittest.main()
