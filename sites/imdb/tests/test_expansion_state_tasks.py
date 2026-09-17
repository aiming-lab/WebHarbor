"""Synthetic offline fixtures only; these are not recorded browser runs."""
import hashlib
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
checks = importlib.import_module("expansion_state_tasks")
from verify_lib import RunEvidence, VerificationError

PASSWORD = "TestPass123!"
EMAILS = {1: "alice.j@test.com", 2: "bob.c@test.com", 4: "david.k@test.com",
          9: "weekend.viewer@test.com"}
HASH = "pbkdf2:sha256:1000$salt$" + hashlib.pbkdf2_hmac(
    "sha256", PASSWORD.encode(), b"salt", 1000).hex()
SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT,name TEXT,password_hash TEXT,created_at TEXT);
CREATE TABLE titles(id INTEGER PRIMARY KEY,tt_id TEXT,primary_title TEXT,original_title TEXT,
 title_type TEXT,year INTEGER,runtime_min INTEGER,rating_avg REAL);
CREATE TABLE genres(id INTEGER PRIMARY KEY,name TEXT,slug TEXT);
CREATE TABLE title_genre(title_id INTEGER,genre_id INTEGER);
CREATE TABLE watchlist_items(id INTEGER PRIMARY KEY,user_id INTEGER,title_id INTEGER,added_at TEXT);
CREATE TABLE user_ratings(id INTEGER PRIMARY KEY,user_id INTEGER,title_id INTEGER,rating INTEGER,created_at TEXT);
CREATE TABLE reviews(id INTEGER PRIMARY KEY,title_id INTEGER,user_id INTEGER,rating INTEGER,
 headline TEXT,body TEXT,helpful_count INTEGER,created_at TEXT,is_seed INTEGER);
CREATE TABLE persons(id INTEGER PRIMARY KEY,name TEXT);
CREATE TABLE credits(id INTEGER PRIMARY KEY,title_id INTEGER,person_id INTEGER,role TEXT);
CREATE TABLE news_items(id INTEGER PRIMARY KEY,headline TEXT);
"""
TITLES = [(1, "Short Alpha", "movie", 1980, 100, 8.4),
          (2, "Short Beta", "movie", 1985, 120, 8.0),
          (3, "Over Limit", "movie", 1981, 121, 9.0),
          (4, "Already Saved", "movie", 1982, 105, 8.8),
          (5, "Ten Star Show", "tvSeries", 1970, 90, 9.5),
          (6, "Outside Years", "movie", 1990, 99, 8.9),
          (7, "Review Film", "movie", 2014, 169, 8.7),
          (8, "Other Unrated", "movie", 2019, 132, 8.5),
          (10, "Weak Signal", "movie", 1975, 95, 7.9)]
ANSWERS = {
    24: "Added Short Alpha (1980), 100 minutes, and Short Beta (1985), 120 minutes. Both are in David's Watchlist.",
    25: "Added Short Alpha (1980). Already Saved (1982) was already saved in David's Watchlist and remains there.",
    26: "Created Weekend Viewer. Review Film (2014) and Other Unrated (2019) remain in the new Watchlist after signing back in.",
    27: 'Review Film (2014): Alice’s review "An earned score" gives 7/10. Saved a personal rating of 7/10 and confirmed My ratings.',
}


class SyntheticExpansionStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.origin = "http://synthetic-new-state.localhost:54321"
        with sqlite3.connect(self.directory / "before.db") as db:
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO users VALUES(?,?,?,?,?)", [
                (u, EMAILS[u], {1: "Alice", 2: "Bob", 4: "David"}[u], HASH, "2024-01-01")
                for u in (1, 2, 4)])
            db.executemany("INSERT INTO titles VALUES(?,?,?,?,?,?,?,?)", [
                (i, f"tt{i:07}", name, "", kind, year, runtime, rating)
                for i, name, kind, year, runtime, rating in TITLES])
            db.execute("INSERT INTO genres VALUES(1,'Sci-Fi','sci-fi')")
            db.executemany("INSERT INTO title_genre VALUES(?,1)", [(i,) for i in (1, 2, 3, 4, 5, 6, 10)])
            db.executemany("INSERT INTO watchlist_items VALUES(?,?,?,?)", [
                (1, 4, 4, "2024-01-01"), (2, 1, 7, "2024-01-01"),
                (3, 1, 8, "2024-01-01"), (4, 1, 4, "2024-01-01")])
            db.executemany("INSERT INTO user_ratings VALUES(?,?,?,?,?)", [
                (1, 2, 1, 10, "2024-01-01"), (2, 2, 4, 10, "2024-01-01"),
                (3, 2, 5, 10, "2024-01-01"), (4, 2, 2, 9, "2024-01-01"),
                (5, 1, 4, 9, "2024-01-01")])
            db.executemany("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)", [
                (1, 7, 1, 7, "An earned score", "Original", 42, "2024-01-01", 0),
                (2, 7, 2, 9, "An earned score", "Distractor", 99, "2024-01-01", 1),
                (3, 8, 2, 8, "Other author", "Other", 10, "2024-01-01", 1)])
            db.execute("INSERT INTO news_items VALUES(1,'Keep unchanged')")
        self.reset_after()

    def reset_after(self):
        shutil.copyfile(self.directory / "before.db", self.directory / "after.db")

    def change(self, sql, parameters=(), both=False):
        for name in (("before.db", "after.db") if both else ("after.db",)):
            with sqlite3.connect(self.directory / name) as db:
                db.execute(sql, parameters)

    def apply_delta(self, number):
        uid, titles = {24: (4, [1, 2]), 25: (4, [1]), 26: (9, [7, 8])}.get(number, (None, []))
        if number == 26:
            self.change("INSERT INTO users VALUES(9,?,?,?,?)", (EMAILS[9], "Weekend Viewer", HASH, "2026-01-01"))
        for i, tid in enumerate(titles):
            self.change("INSERT INTO watchlist_items VALUES(?,?,?,?)", (20 + i, uid, tid, "2026-01-01"))
        if number == 27:
            self.change("INSERT INTO user_ratings VALUES(20,1,7,7,'2026-01-01')")

    def step(self, path, action="observe", params=None, after=None, native=False):
        row = {"url": self.origin + path, "action": action, "params": params or {},
               "action_result": {"success": None if native else True}}
        if after is not None:
            row["url_after"] = self.origin + after
        return row

    def login(self, uid, native=False):
        return [self.step("/login", "fill", {"label": "Email", "value": EMAILS[uid]}),
                self.step("/login", "fill", {"label": "Password", "value": PASSWORD}),
                self.step("/login", "click", {"role": "button", "name": "Sign in"}, "/", native),
                self.step("/")]

    def logout(self, native=False, account=False):
        return [self.step("/account" if account else "/", "click",
                          {"role": "button", "name": "Sign out", "method": "POST"}, "/", native),
                self.step("/")]

    def add(self, tid, chart=False, native=False):
        path = "/chart/top" if chart else f"/title/tt{tid:07}"
        params = ({"selector": "li", "has_link": dict((r[0], r[1]) for r in TITLES)[tid],
                   "child": {"role": "button", "name": "+ Watchlist"}} if chart else
                  {"role": "button", "name": "Add to Watchlist"})
        return [self.step(path, "click", params, path, native), self.step(path)]

    def steps(self, number, chart=False, native=False):
        if number == 24:
            out = self.login(4, native) + [self.step("/list/watchlist"),
                self.step("/search/title?title_type=movie&genre=sci-fi&year_from=1960&year_to=1989&rating_min=8.0")]
            for tid in (1, 2): out += self.add(tid, chart, native)
            return out + [self.step("/list/watchlist")]
        if number == 25:
            return (self.login(2, native) + [self.step("/list/ratings"), self.step("/title/tt0000001"),
                    self.step("/title/tt0000004"), self.step("/title/tt0000005")] + self.logout(native) +
                    self.login(4, native) + [self.step("/list/watchlist")] + self.add(1, chart, native) +
                    [self.step("/list/watchlist")])
        if number == 26:
            out = self.login(1, native) + [self.step("/list/watchlist"), self.step("/list/ratings")] + self.logout(native)
            for field, value in {"name": "Weekend Viewer", "email": EMAILS[9], "password": PASSWORD}.items():
                out.append(self.step("/register", "fill", {"label": field, "value": value}))
            out += [self.step("/register", "click", {"role": "button", "name": "Create account"}, "/", native), self.step("/")]
            for tid in (7, 8): out += self.add(tid, chart, native)
            return out + self.logout(native, account=True) + self.login(9, native) + [self.step("/list/watchlist")]
        return (self.login(1, native) + [self.step("/list/watchlist"), self.step("/list/ratings"),
                self.step("/title/tt0000007/reviews?sort=recent"),
                self.step("/title/tt0000007", "select", {"label": "rating", "value": "7"}),
                self.step("/title/tt0000007", "click", {"role": "button", "name": "Rate"}, "/title/tt0000007", native),
                self.step("/list/ratings")])

    def check(self, number, answer=None, steps=None):
        data = {"task_id": f"IMDb--{number}", "task": "Synthetic contract", "start_url": self.origin + "/",
                "fixture_kind": "synthetic", "steps": self.steps(number) if steps is None else steps,
                "final_answer": ANSWERS[number] if answer is None else answer}
        (self.directory / "trajectory.json").write_text(json.dumps(data))
        with RunEvidence(self.directory, data["task_id"], expected_ques="Synthetic contract") as run:
            return checks.check_expansion_state_task(number, run)

    def test_all_four_exact_changes(self):
        for n in (24, 25, 26, 27):
            with self.subTest(n=n):
                self.reset_after(); self.apply_delta(n); self.assertTrue(self.check(n))

    def test_native_unknown_outcomes_are_corroborated(self):
        for n in (24, 25, 26, 27):
            with self.subTest(n=n):
                self.reset_after(); self.apply_delta(n); self.assertTrue(self.check(n, steps=self.steps(n, native=True)))

    def test_chart_child_add_controls(self):
        for n in (24, 25, 26):
            with self.subTest(n=n):
                self.reset_after(); self.apply_delta(n); self.assertTrue(self.check(n, steps=self.steps(n, chart=True)))

    def test_noop_and_answer_only_fail(self):
        for n in (24, 25, 26, 27):
            with self.subTest(n=n):
                with self.assertRaises(VerificationError): self.check(n)
                self.apply_delta(n)
                with self.assertRaises(VerificationError): self.check(n, steps=[self.step("/")])
                self.reset_after()

    def test_extra_write_or_schema_change_fails(self):
        for sql in ("UPDATE news_items SET headline='Changed'", "CREATE INDEX extra ON users(email)"):
            for n in (24, 25, 26, 27):
                with self.subTest(n=n, sql=sql):
                    self.reset_after(); self.apply_delta(n); self.change(sql)
                    with self.assertRaises(VerificationError): self.check(n)

    def test_foreign_origin_rejected(self):
        self.apply_delta(24); steps = self.steps(24)
        for step in steps:
            for field in ("url", "url_after"):
                if field in step: step[field] = step[field].replace(self.origin, "http://other.localhost:54321")
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_wrong_filter_and_conflicting_duplicate_fail(self):
        self.apply_delta(24)
        for replacement in ("genre=drama", "genre=sci-fi&genre=drama", "genre=sci-fi&rating_min=9"):
            steps = self.steps(24); steps[5]["url"] = steps[5]["url"].replace("genre=sci-fi", replacement)
            with self.subTest(replacement=replacement), self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_filter_numeric_equivalence_and_no_sort_requirement(self):
        self.apply_delta(24); steps = self.steps(24)
        steps[5]["url"] += "&rating_min=8&sort=votes"
        self.assertTrue(self.check(24, steps=steps))

    def test_partial_or_wrong_target(self):
        self.apply_delta(24); self.change("DELETE FROM watchlist_items WHERE title_id=2")
        with self.assertRaises(VerificationError): self.check(24)
        self.change("INSERT INTO watchlist_items VALUES(22,4,3,'2026-01-01')")
        with self.assertRaises(VerificationError): self.check(24)

    def test_wrong_child_or_row_or_nested_metadata_rejected(self):
        self.apply_delta(24)
        for params in ({"role": "button", "name": "Remove from Watchlist"},
                       {"selector": "li", "has_link": "Over Limit", "child": {"name": "Add to Watchlist"}},
                       {"metadata": {"name": "Add to Watchlist"}},
                       {"selector": "li", "has_link": "Short Alpha", "child": {"name": "Details"}}):
            steps = self.steps(24, chart=True); steps[6]["params"] = params
            with self.subTest(params=params), self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_failed_add_cannot_be_used(self):
        self.apply_delta(24); steps = self.steps(24); steps[6]["action_result"]["success"] = False
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_wrong_year_runtime_and_partial_answer(self):
        self.apply_delta(24)
        for a in (ANSWERS[24].replace("1985", "1986"), ANSWERS[24].replace("120 minutes", "119 minutes"),
                  "Added Short Alpha (1980), 100 minutes.", ""):
            with self.subTest(a=a), self.assertRaises(VerificationError): self.check(24, answer=a)

    def test_markdown_fields_and_reverse_order(self):
        self.apply_delta(24)
        a = "| Title | Year | Runtime |\n|---|---|---|\n| Short Beta |1985|120 minutes|\n|Short Alpha|1980|100 minutes|\nBoth added to David's Watchlist."
        self.assertTrue(self.check(24, answer=a))

    def test_chinese_runtime_units_with_existing_watchlist_summary(self):
        self.apply_delta(24)
        answer = ("已新增 Short Alpha（1980，100分钟）和 Short Beta（1985，120分钟）。"
                  "最终 David 的 Watchlist 包含这两部及原有 Already Saved。")
        self.assertTrue(self.check(24, answer=answer))

    def test_cross_account_needs_real_switch(self):
        self.apply_delta(25); steps = self.steps(25)
        steps = [s for s in steps if s["params"].get("name") != "Sign out"]
        with self.assertRaises(VerificationError): self.check(25, steps=steps)

    def test_cross_account_existing_row_cannot_be_replaced(self):
        self.apply_delta(25); self.change("UPDATE watchlist_items SET id=55 WHERE id=1")
        with self.assertRaises(VerificationError): self.check(25)

    def test_already_saved_label_is_not_new_addition(self):
        self.apply_delta(25)
        with self.assertRaises(VerificationError): self.check(25, answer="Added Short Alpha (1980) and Already Saved (1982). Both were newly saved.")
        self.assertTrue(self.check(25, answer="Already saved: Already Saved (1982); Added: Short Alpha (1980). Confirmed David's Watchlist."))

    def test_registration_relogin_required(self):
        self.apply_delta(26); steps = self.steps(26)
        steps = steps[:-7] + [self.step("/list/watchlist")]
        with self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_registration_wrong_password_hash(self):
        self.apply_delta(26); self.change("UPDATE users SET password_hash=? WHERE id=9", (HASH.replace(HASH[-8:], "00000000"),))
        with self.assertRaises(VerificationError): self.check(26)

    def test_registration_wrong_owner(self):
        self.apply_delta(26); self.change("UPDATE watchlist_items SET user_id=1 WHERE id>=20")
        with self.assertRaises(VerificationError): self.check(26)

    def test_get_logout_does_not_clear_identity(self):
        self.apply_delta(26); steps = self.steps(26)
        for step in steps:
            if step["params"].get("name") == "Sign out":
                step["params"]["method"] = "GET"; step["action_result"]["status_code"] = 405
        with self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_bad_login_then_home_visit_is_not_authentication(self):
        self.apply_delta(24); steps = self.steps(24)
        steps[2]["url_after"] = self.origin + "/login"
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_no_password_submission_is_not_login(self):
        self.apply_delta(24); steps = self.steps(24); del steps[1]
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_supplied_password_redaction_uses_snapshot_hash_and_successful_transition(self):
        for marker in ("[SUPPLIED PASSWORD]", "[REDACTED]"):
            for number in (24, 25, 26, 27):
                with self.subTest(marker=marker, number=number):
                    self.reset_after(); self.apply_delta(number); steps = self.steps(number)
                    for step in steps:
                        if step["params"].get("label", "").lower() == "password":
                            step["params"]["value"] = marker
                    self.assertTrue(self.check(number, steps=steps))

    def test_unknown_password_placeholder_is_not_authentication(self):
        self.apply_delta(24); steps = self.steps(24)
        steps[1]["params"]["value"] = "[MASKED]"
        with self.assertRaises(VerificationError):
            self.check(24, steps=steps)

    def test_review_author_derived_score_not_global_or_other_author(self):
        self.apply_delta(27)
        for score in (1, 9, 10):
            self.change("UPDATE user_ratings SET rating=? WHERE id=20", (score,))
            with self.subTest(score=score), self.assertRaises(VerificationError): self.check(27)

    def test_review_featured_route_and_natural_headline(self):
        self.apply_delta(27); steps = self.steps(27); steps[6]["url"] = self.origin + "/title/tt0000007"
        self.assertTrue(self.check(27, steps=steps))

    def test_review_headline_and_saved_score_contradictions(self):
        self.apply_delta(27)
        for answer in (ANSWERS[27].replace("An earned score", "An earned score extra"),
                       ANSWERS[27] + " Current personal rating is 9/10."):
            with self.subTest(answer=answer), self.assertRaises(VerificationError): self.check(27, answer=answer)

    def test_review_source_page_is_required(self):
        for rid in (10, 11, 12):
            self.change("INSERT INTO reviews VALUES(?,7,2,9,'Other','Body',200,'2024-01-01',1)", (rid,), both=True)
        self.apply_delta(27); steps = self.steps(27)
        # Alice's review is outside the three featured rows; title alone no
        # longer exposes the required authored review.
        steps = [s for s in steps if "/reviews" not in s["url"]]
        with self.assertRaises(VerificationError): self.check(27, steps=steps)

    def test_enter_and_index_only_controls(self):
        for n in (24, 26, 27):
            self.reset_after(); self.apply_delta(n); steps = self.steps(n, native=True)
            for step in steps:
                name = step["params"].get("name")
                if name in {"Sign in", "Create account"}:
                    step["action"] = "press"
                    step["params"] = {"selector": "input[name=password]", "key": "Enter"}
                elif name in {"Rate", "Add to Watchlist"}:
                    step["params"] = {"index": 8}
            with self.subTest(n=n): self.assertTrue(self.check(n, steps=steps))

    def test_generic_rating_submit_is_not_a_logout(self):
        self.apply_delta(27); steps = self.steps(27)
        steps[-2]["params"] = {"selector": "button[type=submit]"}
        self.assertTrue(self.check(27, steps=steps))

    def test_foreign_login_destination_not_repaired_by_later_home(self):
        self.apply_delta(24); steps = self.steps(24)
        steps[2]["url_after"] = "http://foreign.localhost:54321/"
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_year_filter_must_parse_like_app(self):
        self.apply_delta(24); steps = self.steps(24)
        steps[5]["url"] = steps[5]["url"].replace("year_from=1960", "year_from=1960.0")
        with self.assertRaises(VerificationError): self.check(24, steps=steps)

    def test_type_filter_route_is_valid_only_for_matching_results(self):
        self.apply_delta(25)
        for valid in (True, False):
            steps = self.steps(25)
            steps[5:8] = [self.step("/search/title?title_type=movie" + ("" if valid else "&year_from=2000")),
                          self.step("/search/title?title_type=tvSeries")]
            if valid: self.assertTrue(self.check(25, steps=steps))
            else:
                with self.assertRaises(VerificationError): self.check(25, steps=steps)

    def test_source_and_destination_can_be_read_in_either_order(self):
        self.apply_delta(25)
        steps = self.login(4) + [self.step("/list/watchlist")] + self.logout()
        steps += self.login(2) + [self.step("/list/ratings"), self.step("/title/tt0000001"),
                                 self.step("/title/tt0000004"), self.step("/title/tt0000005")]
        steps += self.logout() + self.login(4) + self.add(1) + [self.step("/list/watchlist")]
        self.assertTrue(self.check(25, steps=steps))

    def test_registration_may_reauthenticate_before_saving(self):
        self.apply_delta(26); steps = self.steps(26)
        registered = next(i for i,s in enumerate(steps) if s["params"].get("name") == "Create account")
        steps[registered+2:registered+2] = self.logout() + self.login(9)
        self.assertTrue(self.check(26, steps=steps))

    def test_registration_form_values_must_match_submitted_account(self):
        self.apply_delta(26); steps = self.steps(26)
        for step in steps:
            if step["url"].endswith("/register") and step["params"].get("label") == "name":
                step["params"]["value"] = "Wrong name"
        with self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_review_correct_global_rating_is_not_personal_score(self):
        self.apply_delta(27)
        self.assertTrue(self.check(27, answer=ANSWERS[27] + " IMDb rating is 8.7/10."))

    def test_review_wrong_explicit_author_fails(self):
        self.apply_delta(27)
        with self.assertRaises(VerificationError): self.check(27, answer=ANSWERS[27].replace("Alice’s", "Bob’s"))

    def test_added_recommendation_cannot_be_reported_as_preexisting(self):
        self.apply_delta(25)
        with self.assertRaises(VerificationError):
            self.check(25, answer="Short Alpha (1980) was already saved. Already Saved (1982) was also already saved.")

    def test_persistence_relogin_must_follow_all_additions(self):
        self.apply_delta(26); steps = self.steps(26)
        tail = steps[-7:-1]
        steps = steps[:-7]
        first_add = next(i for i, s in enumerate(steps) if s["params"].get("name") == "Add to Watchlist")
        steps[first_add:first_add] = tail
        steps.append(self.step("/list/watchlist"))
        with self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_indexed_logout_requires_guarded_auth_page_transition(self):
        self.apply_delta(26); steps = self.steps(26, native=True)
        for step in steps:
            if step["params"].get("name") == "Sign out":
                step["params"] = {"index": 3, "method": "POST"}
        self.assertTrue(self.check(26, steps=steps))
        for step in steps:
            if step["params"].get("method") == "POST": step["params"]["method"] = "HEAD"
        with self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_indexed_add_cannot_be_logout_if_next_route_is_title(self):
        self.apply_delta(24); steps = self.steps(24, native=True)
        for step in steps:
            if step["params"].get("name") == "Add to Watchlist": step["params"] = {"index": 3}
        self.assertTrue(self.check(24, steps=steps))

    def test_indexed_logout_retains_explicit_ancestor_constraints(self):
        self.apply_delta(26)
        for target in ("http://foreign.localhost:54321/logout", "/title/tt0000007/watchlist"):
            steps = self.steps(26, native=True)
            for step in steps:
                if step["params"].get("name") == "Sign out":
                    step["params"] = {"selector": f'form[action="{target}"]', "method": "POST", "child": {"index": 3}}
            with self.subTest(target=target), self.assertRaises(VerificationError): self.check(26, steps=steps)

    def test_numeric_out_of_ten_score_and_contradiction(self):
        self.apply_delta(27)
        a = 'Review Film (2014): Alice’s review "An earned score". I saved 7 out of 10 as the personal rating and confirmed My ratings.'
        self.assertTrue(self.check(27, answer=a))
        with self.assertRaises(VerificationError): self.check(27, answer=a + " The personal score is 9 out of 10.")

    def test_duplicate_add_claim_and_negated_claim(self):
        self.apply_delta(25)
        a = "Added Short Alpha (1980). Already Saved (1982) was already in David's Watchlist, and I added it again."
        with self.assertRaises(VerificationError): self.check(25, answer=a)
        self.assertTrue(self.check(25, answer=a.replace("I added it again", "I did not add it again")))


class BoundedPasswordTests(unittest.TestCase):
    def test_pbkdf2_correct_and_wrong(self):
        self.assertTrue(checks.verify_password(HASH, PASSWORD))
        self.assertFalse(checks.verify_password(HASH, "wrong"))

    def test_scrypt_actual_werkzeug_shape(self):
        digest = hashlib.scrypt(PASSWORD.encode(), salt=b"salt", n=32768, r=8, p=1, maxmem=64*1024*1024).hex()
        self.assertTrue(checks.verify_password("scrypt:32768:8:1$salt$" + digest, PASSWORD))

    def test_malformed_or_resource_exhausting_hashes_fail(self):
        for value in ("plain$password", "pbkdf2:md5:1$salt$00", "pbkdf2:sha256:999999999$salt$00",
                      "scrypt:1073741824:8:1$salt$00", "scrypt:3:8:1$salt$00", HASH + "$extra"):
            with self.subTest(value=value): self.assertFalse(checks.verify_password(value, PASSWORD))

    def test_non_strings_and_invalid_unicode_fail_closed(self):
        self.assertFalse(checks.verify_password({}, []))
        self.assertFalse(checks.verify_password(HASH, "\ud800"))

    def test_pbkdf2_sha512_preserves_password_whitespace(self):
        password = " TestPass123! "
        digest = hashlib.pbkdf2_hmac("sha512", password.encode(), b"salt", 1000).hex()
        encoded = "pbkdf2:sha512:1000$salt$" + digest
        self.assertTrue(checks.verify_password(encoded, password))
        self.assertFalse(checks.verify_password(encoded, password.strip()))


if __name__ == "__main__":
    unittest.main()
