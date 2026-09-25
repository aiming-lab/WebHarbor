"""Synthetic verifier fixtures; these tests are not real browser-run evidence."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "verify" / "verify_lib.py"
SPEC = importlib.util.spec_from_file_location("imdb_verify_lib", MODULE_PATH)
verify_lib = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_lib)
RunEvidence = verify_lib.RunEvidence
VerificationError = verify_lib.VerificationError


class SyntheticRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.origin = "http://synthetic-audit.localhost:48015"
        self.trajectory = {
            "task_id": "IMDb--synthetic",
            "task": "Open the movie chart.",
            "start_url": self.origin + "/",
            "final_answer": "Synthetic answer.",
            "fixture_kind": "synthetic",
            "steps": [],
        }
        for name in ("before.db", "after.db"):
            with sqlite3.connect(self.run / name) as db:
                db.executescript(
                    "CREATE TABLE ratings (id INTEGER PRIMARY KEY, rating INTEGER);"
                    "INSERT INTO ratings VALUES (1, 7);"
                    "CREATE TABLE users (id INTEGER, password_hash TEXT);"
                    "INSERT INTO users VALUES (1, 'synthetic-secret-hash');"
                    "CREATE TABLE duplicates (value);"
                    "INSERT INTO duplicates VALUES ('same'), ('same');"
                )

    def load(self, **kwargs):
        (self.run / "trajectory.json").write_text(json.dumps(self.trajectory))
        return RunEvidence(self.run, "IMDb--synthetic", **kwargs)

    def step(self, path, after=None, success=True, **extra):
        step = {"url": self.origin + path, "action": "click"}
        if after is not None:
            step["url_after"] = self.origin + after
        if success is not None:
            step["action_result"] = {"success": success, "error": None}
        step.update(extra)
        self.trajectory["steps"].append(step)
        return step

    def test_local_start_hosts_and_runtime_port_override(self):
        for origin in ("http://localhost:48015", "http://127.0.0.1:54321",
                       "http://[::1]:12345", "http://fresh.case.localhost:48015"):
            with self.subTest(origin=origin):
                self.trajectory["start_url"] = origin + "/"
                self.trajectory["steps"] = [{"url": origin + "/chart/top"}]
                with self.load() as run:
                    self.assertTrue(run.visited("/chart/top"))

    def test_foreign_start_urls_rejected(self):
        for url in ("https://localhost:48015/", "http://imdb.com/",
                    "http://localhost.evil/", "http://localhost@evil/",
                    "http://user@localhost/", "http://localhost:bad/",
                    "http://localhost:99999/", "file:///localhost/chart/top",
                    " http://localhost/", "http://bad..localhost/"):
            with self.subTest(url=url):
                self.trajectory["start_url"] = url
                with self.assertRaises(VerificationError):
                    self.load()

    def test_foreign_events_same_path_and_embedded_path_do_not_count(self):
        self.trajectory["steps"] = [
            {"url": url, "url_after": url, "action_result": {"success": True}}
            for url in (
                "http://evil.example/chart/top",
                "http://localhost:48015/chart/top",
                "http://synthetic-audit.localhost:48016/chart/top",
                "https://synthetic-audit.localhost:48015/chart/top",
                "http://evil.example/?next=/chart/top",
                "http://user@synthetic-audit.localhost:48015/chart/top",
                "/chart/top",
            )
        ]
        with self.load() as run:
            self.assertFalse(run.visited("/chart/top"))
            self.assertEqual(run.events, [])

    def test_default_http_port_and_hostname_case_are_equivalent(self):
        self.trajectory["start_url"] = "http://LOCALHOST/"
        self.trajectory["steps"] = [{"url": "http://localhost:80/chart/top"}]
        with self.load() as run:
            self.assertTrue(run.visited("/chart/top"))

    def test_failed_after_url_does_not_prove_navigation(self):
        self.step("/title/A", "/name/B", success=False, status="failed")
        with self.load() as run:
            self.assertTrue(run.visited("/title/A"))
            self.assertFalse(run.visited("/name/B"))
            self.assertEqual(run.successful_steps(), [])
            self.assertEqual(run.events[0]["phase"], "before")
        self.step("/name/B", success=None)
        with self.load() as run:
            self.assertTrue(run.visited("/name/B"))

    def test_failure_overrides_other_success_flags_and_unknown_is_not_success(self):
        self.step("/", "/failed", status="completed",
                  action_result={"success": True, "error": "failure"})
        self.step("/", "/failed-status", status="failed")
        self.step("/", "/unknown", action_result={"success": None, "error": None})
        self.step("/", "/completed", success=None, status="completed")
        with self.load() as run:
            self.assertFalse(run.visited("/failed"))
            self.assertFalse(run.visited("/failed-status"))
            self.assertFalse(run.visited("/unknown"))
            self.assertTrue(run.visited("/completed"))
            self.assertEqual(len(run.successful_steps()), 1)

    def test_malformed_success_status_does_not_crash_or_prove_navigation(self):
        self.step("/", "/bad-status", status={"completed": True})
        self.step("/", "/bad-success", status="completed", action_result={"success": "false"})
        with self.load() as run:
            self.assertFalse(run.visited("/bad-status"))
            self.assertFalse(run.visited("/bad-success"))
            self.assertEqual(run.successful_steps(), [])

    def test_tail_slash_query_subsets_and_decoding(self):
        url = "/search/title/?genres=crime&genres=drama&tag=a&tag=a&q=dark+knight&blank="
        self.step(url)
        with self.load() as run:
            self.assertTrue(run.visited("/search/title"))
            self.assertTrue(run.visited("/search/title/", {"genres": ["crime"]}))
            self.assertTrue(run.visited("/search/title", {"tag": ["a", "a"]}))
            self.assertFalse(run.visited("/search/title", {"tag": ["a", "a", "a"]}))
            self.assertTrue(run.visited("/search/title", {"q": ["dark knight"], "blank": [""]}))
            self.assertFalse(run.visited("/search/title", {"absent": [""]}))
            self.assertFalse(run.visited("/SEARCH/title"))
            self.assertFalse(run.visited("/search"))
            self.assertEqual(run.visit_urls("/search/title"), [self.origin + url])

    def test_ordered_visits_require_each_event_but_no_implicit_home(self):
        self.step("/B", "/A")
        with self.load() as run:
            self.assertTrue(run.visited("/A"))
            self.assertTrue(run.visited("/B"))
            self.assertTrue(run.has_ordered_visits(["/B", "/A"]))
            self.assertFalse(run.has_ordered_visits(["/A", "/B"]))
            self.assertFalse(run.has_ordered_visits(["/B", "/A", "/B"]))
            self.assertFalse(run.visited("/"))

    def test_start_url_alone_is_not_visit_evidence(self):
        with self.load() as run:
            self.assertFalse(run.visited("/"))

    def test_wrong_task_replay_and_question_replay_rejected(self):
        self.trajectory["task_id"] = "IMDb--other"
        with self.assertRaisesRegex(VerificationError, "task ID"):
            self.load()
        self.trajectory["task_id"] = "IMDb--synthetic"
        with self.assertRaisesRegex(VerificationError, "question"):
            self.load(expected_ques="Open the other chart.")
        del self.trajectory["task"]
        with self.assertRaises(VerificationError):
            self.load(expected_ques="Open the movie chart.")

    def test_question_whitespace_only_normalization_and_final_answer(self):
        self.trajectory["task"] = "  Open\n the movie\tchart.  "
        with self.load(expected_ques="Open the movie chart.") as run:
            self.assertEqual(run.answer, "Synthetic answer.")
        self.trajectory["task"] = "Open themovie chart."
        with self.assertRaises(VerificationError):
            self.load(expected_ques="Open the movie chart.")

    def test_missing_snapshots_fail_without_live_fallback(self):
        (self.run / "before.db").unlink()
        with self.assertRaisesRegex(VerificationError, "initial"):
            self.load()
        self.assertFalse((self.run / "before.db").exists())
        (self.run / "after.db").rename(self.run / "initial.db")
        with self.assertRaisesRegex(VerificationError, "after"):
            self.load()

    def test_initial_filename_and_explicit_overrides(self):
        (self.run / "before.db").rename(self.run / "initial.db")
        with self.load() as run:
            self.assertEqual(run.diff_tables(), {})
        (self.run / "initial.db").rename(self.run / "explicit-before.db")
        with self.load(initial_db=self.run / "explicit-before.db") as run:
            self.assertEqual(run.diff_tables(), {})

    def test_connections_are_readonly_rows_and_closed(self):
        with self.load() as run:
            conn = run.initial
            self.assertIsInstance(conn.execute("SELECT * FROM ratings").fetchone(), sqlite3.Row)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("UPDATE ratings SET rating=9")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_multiset_change_and_extra_table_write_detected_without_secret_log(self):
        with sqlite3.connect(self.run / "after.db") as db:
            db.execute("UPDATE ratings SET rating=8")
            db.execute("UPDATE users SET password_hash='another-synthetic-hash'")
            db.execute("DELETE FROM duplicates WHERE rowid=1")
        with self.load() as run:
            diff = run.diff_tables()
            self.assertEqual(diff["ratings"]["columns"], ["id", "rating"])
            self.assertEqual(diff["ratings"]["before"], [{"id": 1, "rating": 7}])
            self.assertEqual(diff["ratings"]["after"], [{"id": 1, "rating": 8}])
            self.assertEqual(diff["duplicates"]["before"], [{"value": "same"}])
            self.assertEqual(diff["duplicates"]["after"], [])
            with self.assertRaises(VerificationError) as error:
                run.assert_unchanged(except_tables=("ratings", "duplicates"))
            self.assertIn("users", str(error.exception))
            self.assertNotIn("hash", str(error.exception))
            run.assert_unchanged(except_tables=("ratings", "users", "duplicates"))

    def test_reordered_rows_are_unchanged(self):
        with sqlite3.connect(self.run / "after.db") as db:
            db.execute("DELETE FROM duplicates")
            db.executemany("INSERT INTO duplicates VALUES (?)", [("same",), ("same",)])
        with self.load() as run:
            run.assert_unchanged()

    def test_empty_business_table_added_removed_or_schema_changed(self):
        with sqlite3.connect(self.run / "before.db") as db:
            db.execute("CREATE TABLE removed (a TEXT)")
            db.execute("CREATE TABLE altered (a TEXT)")
        with sqlite3.connect(self.run / "after.db") as db:
            db.execute("CREATE TABLE added (a TEXT)")
            db.execute("CREATE TABLE altered (a INTEGER)")
        with self.load() as run:
            diff = run.diff_tables()
            self.assertEqual(set(diff), {"removed", "added", "altered"})
            self.assertTrue(all(row["schema_changed"] for row in diff.values()))
            with self.assertRaises(VerificationError):
                run.assert_unchanged()

    def test_storage_types_and_null_are_not_stringified(self):
        with sqlite3.connect(self.run / "before.db") as db:
            db.executemany("INSERT INTO duplicates VALUES (?)", [(None,), (1,), (b"1",)])
        with sqlite3.connect(self.run / "after.db") as db:
            db.executemany("INSERT INTO duplicates VALUES (?)", [(None,), ("1",), (b"1",)])
        with self.load() as run:
            diff = run.diff_tables()["duplicates"]
            self.assertEqual(diff["before"], [{"value": 1}])
            self.assertEqual(diff["after"], [{"value": "1"}])

    def test_sqlite_internal_tables_are_ignored(self):
        for name in ("before.db", "after.db"):
            with sqlite3.connect(self.run / name) as db:
                db.execute("CREATE TABLE counted (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        with sqlite3.connect(self.run / "after.db") as db:
            db.execute("INSERT INTO counted DEFAULT VALUES")
            db.execute("DELETE FROM counted")
        with self.load() as run:
            run.assert_unchanged()

    def test_emit_result_is_one_json_object_and_exit_status(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = verify_lib.emit_result("IMDb--synthetic", False, "Synthetic failure", ["table changed"])
        self.assertEqual(code, 1)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result, {"task_id": "IMDb--synthetic", "pass": False,
                                  "reason": "Synthetic failure", "evidence": ["table changed"]})

    def test_cli_arguments(self):
        args = verify_lib.parse_args(["--run_dir", str(self.run), "--initial_db", "a.db", "--after_db", "b.db"])
        self.assertEqual(args.run_dir, str(self.run))
        self.assertEqual(args.initial_db, "a.db")
        self.assertEqual(args.after_db, "b.db")


if __name__ == "__main__":
    unittest.main()
