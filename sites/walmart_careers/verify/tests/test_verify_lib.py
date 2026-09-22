from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _support import State  # noqa: E402
from verify_lib import (  # noqa: E402
    application_rows,
    contains_confirmation_number,
    contains_count,
    contains_hashtag,
    contains_req_id,
    contains_shift_window,
    contains_street,
    is_walmart_careers_site_url,
    job_detail_visited,
    mentions_store_number,
    navigated_to_path,
    new_application_rows,
    new_user_ids,
    results_visited,
    rows_unchanged_except,
    saved_job_ids,
    saved_jobs_delta,
    tables_unchanged,
    trajectory_last_email,
    user_profile,
)


def traj(*urls: str) -> dict:
    return {"steps": [{"url": url, "action": "click", "params": {}} for url in urls]}


class UrlGateTests(unittest.TestCase):
    def test_loopback_origins_on_any_port(self) -> None:
        for url in (
            "http://localhost:40023/jobs/CP-1-1",
            "http://127.0.0.1:41023/jobs/CP-1-1?x=1",
            "http://[::1]:5017/jobs/CP-1-1",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_walmart_careers_site_url(url))
                self.assertTrue(navigated_to_path(traj(url), "/jobs/CP-1-1"))

    def test_external_and_non_http_rejected(self) -> None:
        for url in ("https://careers.walmart.com/jobs/CP-1-1", "/jobs/CP-1-1", "file:///jobs/CP-1-1"):
            with self.subTest(url=url):
                self.assertFalse(is_walmart_careers_site_url(url))
                self.assertFalse(navigated_to_path(traj(url), "/jobs/CP-1-1"))

    def test_job_detail_is_exact(self) -> None:
        self.assertTrue(job_detail_visited(traj("http://localhost:41023/jobs/CP-5991-12522/"), "CP-5991-12522"))
        self.assertFalse(job_detail_visited(traj("http://localhost:41023/jobs/CP-5991-12522/apply"), "CP-5991-12522"))
        self.assertFalse(job_detail_visited(traj("http://localhost:41023/jobs/CP-5991-11940"), "CP-5991-12522"))

    def test_start_url_counts(self) -> None:
        self.assertTrue(navigated_to_path({"start_url": "http://localhost:40023/", "steps": []}, "/"))

    def test_results_text_params(self) -> None:
        t = traj("http://localhost:41023/results?q=Yard+Driver+roles")
        self.assertTrue(results_visited(t, q="yard"))
        self.assertTrue(results_visited(traj("http://localhost:41023/results?searchQuery=yard"), q="yard"))
        self.assertFalse(results_visited(t, q="optician"))
        self.assertFalse(results_visited(traj("http://localhost:41023/?q=yard"), q="yard"))

    def test_results_facets_are_exact(self) -> None:
        t = traj("http://localhost:41023/results?brand=Sam%27s+Club&type=Part+time&shift=Weekend+Overnight&loc=Plano%2C+TX&radius=25")
        self.assertTrue(results_visited(t, shift="Weekend Overnight", type="Part time", brand="Sam's Club"))
        self.assertTrue(results_visited(t, loc="plano"))
        self.assertFalse(results_visited(t, shift="Weekend"))
        self.assertFalse(results_visited(t, type="Full time"))

    def test_results_alternatives_and_regex(self) -> None:
        alternatives = ("puerto rico", re.compile(r"\bpr\b"))
        self.assertTrue(results_visited(traj("http://localhost:41023/results?loc=Bayamon%2C+PR"), loc=alternatives))
        self.assertTrue(results_visited(traj("http://localhost:41023/results?loc=puerto+rico"), loc=alternatives))
        self.assertFalse(results_visited(traj("http://localhost:41023/results?loc=Springfield"), loc=alternatives))

    def test_last_email_input(self) -> None:
        t = {"steps": [
            {"action": "input", "params": {"text": "alice.j@test.com"}},
            {"action": "input", "params": {"text": "TestPass123!"}},
            {"action": "input", "params": {"text": "Bob.C@test.com"}},
        ]}
        self.assertEqual(trajectory_last_email(t), "bob.c@test.com")


class MatcherTests(unittest.TestCase):
    def test_requisition_ids(self) -> None:
        self.assertTrue(contains_req_id("id cp–5991–12522.", "CP-5991-12522"))
        self.assertTrue(contains_req_id("CP - 954 - 10637", "CP-954-10637"))
        self.assertFalse(contains_req_id("CP-5991-125220", "CP-5991-12522"))
        self.assertFalse(contains_req_id("XCP-5991-12522", "CP-5991-12522"))
        self.assertFalse(contains_req_id("R-2468347", "R-2411489"))
        self.assertFalse(contains_req_id("The requisition is not CP-5991-12522.", "CP-5991-12522"))

    def test_streets(self) -> None:
        self.assertTrue(contains_street("2441 South Rock Road", "2441 S Rock Rd"))
        self.assertTrue(contains_street("2101 Southeast Simple Savings Drive", "2101 SE Simple Savings Dr"))
        self.assertTrue(contains_street("8109 Merrimac Trl", "8109 Merrimac Trail"))
        self.assertTrue(contains_street("Carr 2 KM 11.4, Bayamon", "Carr 2 KM 11.4"))
        self.assertFalse(contains_street("2441 S Maize Rd", "2441 S Rock Rd"))
        self.assertFalse(contains_street("12441 S Rock Rd", "2441 S Rock Rd"))
        self.assertFalse(contains_street("The address is not 2441 S Rock Rd.", "2441 S Rock Rd"))
        self.assertFalse(contains_street("2441 Rock", "2441 S Rock Rd"))
        self.assertFalse(contains_street("2441 S Rock", "2441 S Rock Rd"))

    def test_shift_windows(self) -> None:
        self.assertTrue(contains_shift_window("6:00pm - 3:00am", "6:00pm", "3:00am"))
        self.assertTrue(contains_shift_window("6 PM to 3 a.m.", "6:00pm", "3:00am"))
        self.assertTrue(contains_shift_window("18:00–03:00", "6:00pm", "3:00am"))
        self.assertTrue(contains_shift_window("noon to 5:00 pm", "12:00pm", "5:00pm"))
        self.assertFalse(contains_shift_window("6:00am - 3:00am", "6:00pm", "3:00am"))
        self.assertFalse(contains_shift_window("9:00pm - 1:30am", "3:00pm", "7:30pm"))
        self.assertFalse(contains_shift_window("The window is not 6:00pm - 3:00am", "6:00pm", "3:00am"))

    def test_counts_ignore_ids_times_money_streets(self) -> None:
        text = "CP-5991-12522 at 2441 S Rock Rd, store #5991, $17.00-$19.50/hr, 6:00pm-3:00am, zip 67207: 3 open positions"
        self.assertTrue(contains_count(text, 3))
        for wrong in (5991, 12522, 2441, 17, 19, 6, 67207):
            with self.subTest(wrong=wrong):
                self.assertFalse(contains_count(text, wrong))
        self.assertTrue(contains_count("three open positions", 3))
        self.assertFalse(contains_count("Option 2 requires 9 years", 2))
        self.assertTrue(contains_count("Option 2 requires 9 years", 9))
        self.assertFalse(contains_count("3rd shift", 3))

    def test_counts_survive_sentence_punctuation(self) -> None:
        # Real nano runs on tasks 3 and 4 wrote the count right before a period.
        self.assertTrue(contains_count("Hashtag: #pharmacytechjobs. Open positions: 2.", 2))
        self.assertTrue(contains_count("Requisition ID: CP-4750-11130; Open positions: 3.", 3))
        self.assertTrue(contains_count("Open positions: 2, hashtag #x", 2))
        self.assertFalse(contains_count("2.5 open positions", 2))
        self.assertFalse(contains_count("about 2,000 roles", 2))
        self.assertFalse(contains_count("12.", 2))
        self.assertFalse(contains_count("There are not 2 open positions.", 2))

    def test_store_numbers(self) -> None:
        self.assertTrue(mentions_store_number("Store #1230 has more", 1230))
        self.assertTrue(mentions_store_number("store 1230", 1230))
        self.assertFalse(mentions_store_number("CP-1230-11592 has 5", 1230))
        self.assertFalse(mentions_store_number("zip 39601", 3960))

    def test_hashtags_and_confirmations(self) -> None:
        self.assertTrue(contains_hashtag("ends with #PharmacyTechJobs.", "#pharmacytechjobs"))
        self.assertFalse(contains_hashtag("#pharmacytechjobs2", "#pharmacytechjobs"))
        self.assertTrue(contains_confirmation_number("Confirmation: wmc–000005", "WMC-000005"))
        self.assertFalse(contains_confirmation_number("WMC-0000050", "WMC-000005"))
        self.assertFalse(contains_confirmation_number("It is not WMC-000005.", "WMC-000005"))


class StateHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.initial = State().write(root / "initial.db")
        after_state = State()
        after_state.add_saved(1, "CP-6088-10659")
        after_state.remove_saved(2, "CP-5991-11940")
        after_state.set_profile(4, city="Rogers", state="AR")
        self.new_user = after_state.add_user("new.candidate@test.com")
        self.confirmation = after_state.add_application("CP-4137-10959", 3, "carol.d@test.com", "(253) 555-0142")
        self.after = after_state.write(root / "after.db")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_saved_jobs(self) -> None:
        self.assertEqual(saved_jobs_delta(self.initial, self.after, "alice.j@test.com"), ({"CP-6088-10659"}, set()))
        self.assertEqual(saved_jobs_delta(self.initial, self.after, "bob.c@test.com"), (set(), {"CP-5991-11940"}))
        self.assertIsNone(saved_job_ids(self.initial, "nobody@test.com"))
        self.assertEqual(len(saved_job_ids(self.initial, "alice.j@test.com")), 6)

    def test_applications(self) -> None:
        rows = new_application_rows(self.initial, self.after)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["confirmation_no"], self.confirmation)
        self.assertEqual(self.confirmation, "WMC-000005")
        self.assertEqual(len(application_rows(self.after, job_id="CP-4137-10959", phone_digits="2535550142")), 1)
        self.assertEqual(application_rows(self.after, job_id="CP-4137-10959", phone_digits="2535550119"), [])
        self.assertEqual(application_rows(self.initial, email="DAVID.K@test.com")[0]["confirmation_no"], "WMC-000004")

    def test_users(self) -> None:
        self.assertEqual(new_user_ids(self.initial, self.after), {self.new_user})
        self.assertEqual(user_profile(self.after, "david.k@test.com")["city"], "Rogers")
        self.assertEqual(user_profile(self.initial, "david.k@test.com")["state"], "TX")
        self.assertFalse(rows_unchanged_except(self.initial, self.after, "users", []))
        self.assertTrue(rows_unchanged_except(self.initial, self.after, "users", [4, self.new_user]))

    def test_tables_unchanged(self) -> None:
        self.assertEqual(
            tables_unchanged(self.initial, self.after, ("users", "saved_jobs", "applications")),
            {"users": False, "saved_jobs": False, "applications": False},
        )
        self.assertEqual(tables_unchanged(self.initial, self.initial, ("saved_jobs",)), {"saved_jobs": True})


if __name__ == "__main__":
    unittest.main()
