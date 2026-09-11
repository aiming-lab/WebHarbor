from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_lib as lib  # noqa: E402
from _support import BASE, State, step  # noqa: E402


def traj(*steps: dict) -> dict:
    return {"start_url": f"{BASE}/", "steps": list(steps)}


class NormalizeAndPhraseTests(unittest.TestCase):
    def test_normalize_folds_case_dashes_and_ampersand(self) -> None:
        self.assertEqual(lib.normalize_text("Rose Tree Orthopedics & Sports Medicine"), "rose tree orthopedics and sports medicine")
        self.assertEqual(lib.normalize_text("Riverfront – Wellness"), "riverfront - wellness")

    def test_phrase_ignores_punctuation_and_dash_style(self) -> None:
        self.assertTrue(lib.contains_institution("Office: Providence Road Medical Group – Professional Plaza.", "Providence Road Medical Group - Professional Plaza"))
        self.assertTrue(lib.contains_institution("rose tree orthopedics and sports medicine", "Rose Tree Orthopedics & Sports Medicine"))
        self.assertFalse(lib.contains_institution("Blue Ridge Medical Center", "Blue Ridge Regional Medical Center"))

    def test_phrase_requires_whole_tokens_and_affirmation(self) -> None:
        self.assertFalse(lib.contains_phrase("Anemias", "Anemia"))
        self.assertFalse(lib.contains_phrase("It is not Anemia.", "Anemia"))
        self.assertFalse(lib.contains_phrase("Anemia is wrong; the answer is Hepatitis C", "Anemia"))
        self.assertTrue(lib.contains_phrase("First entry: Anemia.", "Anemia"))

    def test_condition_accepts_abbreviation_or_long_form(self) -> None:
        self.assertTrue(lib.contains_condition("marked More Than Most: GERD", "Acid Reflux (GERD)"))
        self.assertTrue(lib.contains_condition("acid reflux", "Acid Reflux (GERD)"))
        self.assertFalse(lib.contains_condition("Celiac Disease", "Acid Reflux (GERD)"))

    def test_doctor_name_needs_both_tokens(self) -> None:
        self.assertTrue(lib.contains_doctor_name("Dr. Emerson Huang, DO", "Emerson", "Huang"))
        self.assertTrue(lib.contains_doctor_name("Huang, Emerson", "Emerson", "Huang"))
        self.assertFalse(lib.contains_doctor_name("Dr. Huang graduated first", "Emerson", "Huang"))


class NumberMatcherTests(unittest.TestCase):
    def test_year(self) -> None:
        self.assertTrue(lib.contains_year("graduated in 2004.", 2004))
        self.assertFalse(lib.contains_year("NPI 1200412345", 2004))
        self.assertFalse(lib.contains_year("not 2004 but 2008", 2004))

    def test_npi(self) -> None:
        self.assertTrue(lib.contains_npi("NPI: 1438496704", "1438496704"))
        self.assertTrue(lib.contains_npi("NPI 1438 496 704", "1438496704"))
        self.assertFalse(lib.contains_npi("NPI 14384967041", "1438496704"))
        self.assertFalse(lib.contains_npi("NPI 1438496705", "1438496704"))

    def test_phone(self) -> None:
        for text in ("(302) 555-1542", "302-555-1542", "302.555.1542", "+1 302 555 1542", "call 3025551542 now"):
            self.assertTrue(lib.contains_phone(text, "(302) 555-1542"), text)
        self.assertFalse(lib.contains_phone("(302) 555-4822", "(302) 555-1542"))
        self.assertFalse(lib.contains_phone("13025551542999", "(302) 555-1542"))

    def test_hours_window(self) -> None:
        for text in ("8:00 am - 1:00 pm", "8 AM to 1 PM", "08:00-13:00", "8:00 a.m. until 1:00 p.m."):
            self.assertTrue(lib.contains_hours_window(text, "8:00 am", "1:00 pm"), text)
        self.assertFalse(lib.contains_hours_window("8:00 am - 5:00 pm", "8:00 am", "1:00 pm"))
        self.assertFalse(lib.contains_hours_window("Closed", "8:00 am", "1:00 pm"))

    def test_minutes_masks_clock_times(self) -> None:
        self.assertTrue(lib.contains_minutes("Average wait time 15 minutes", 15))
        self.assertTrue(lib.contains_minutes("15 min", 15))
        self.assertTrue(lib.contains_minutes("a 15-minute wait", 15))
        self.assertTrue(lib.contains_minutes("average wait time: 15", 15))
        self.assertFalse(lib.contains_minutes("opens at 9:15 am", 15))
        self.assertFalse(lib.contains_minutes("wait 45 minutes", 15))
        self.assertFalse(lib.contains_minutes("wait 150 minutes", 15))

    def test_star_rating(self) -> None:
        for text in ("4 stars", "4-star", "rated 4/5", "4.0 out of 5", "four stars", "rating: 4", "★★★★"):
            self.assertTrue(lib.contains_star_rating(text, 4), text)
        for text in ("5 stars", "★★★★★", "November 4, 2022", "4 reviews", "not 4 stars"):
            self.assertFalse(lib.contains_star_rating(text, 4), text)

    def test_review_date(self) -> None:
        when = dt.date(2022, 11, 2)
        for text in ("November 2, 2022", "Nov 2 2022", "Nov. 2nd, 2022", "2 November 2022", "2022-11-02", "11/2/2022", "11/02/22"):
            self.assertTrue(lib.contains_review_date(text, when), text)
        for text in ("November 3, 2022", "November 2, 2023", "December 2, 2022", "2022-11-20"):
            self.assertFalse(lib.contains_review_date(text, when), text)

    def test_street(self) -> None:
        self.assertTrue(lib.contains_street("3543 Baltimore Pike Bldg B", "3543 Baltimore Pike"))
        self.assertTrue(lib.contains_street("2441 South Rock Road", "2441 S Rock Rd"))
        self.assertFalse(lib.contains_street("3534 Baltimore Pike", "3543 Baltimore Pike"))

    def test_reference(self) -> None:
        self.assertTrue(lib.contains_reference("Reference WMD-AB2CD3EF.", "WMD-AB2CD3EF"))
        self.assertTrue(lib.contains_reference("wmd–ab2cd3ef", "WMD-AB2CD3EF"))
        self.assertTrue(lib.contains_reference("WMD AB2CD3EF", "WMD-AB2CD3EF"))
        self.assertFalse(lib.contains_reference("WMD-AB2CD3EFX", "WMD-AB2CD3EF"))
        self.assertEqual(lib.extract_references("WMD-AB2CD3EF and WMD-JASDV25V"), {"WMD-AB2CD3EF", "WMD-JASDV25V"})

    def test_url(self) -> None:
        site = "https://www.rosetreeorthopedicssportsmedicine.example"
        for text in (site, "rosetreeorthopedicssportsmedicine.example", "http://rosetreeorthopedicssportsmedicine.example/", "Website: www.rosetreeorthopedicssportsmedicine.example."):
            self.assertTrue(lib.contains_url(text, site), text)
        self.assertFalse(lib.contains_url("https://www.rosetreeorthopedicssportsmedicine.com", site))
        self.assertFalse(lib.contains_url("xrosetreeorthopedicssportsmedicine.example", site))

    def test_review_text_matches(self) -> None:
        expected = "Short wait and a clear explanation of my treatment options."
        self.assertTrue(lib.review_text_matches("short  wait and a clear explanation of my treatment options", expected))
        self.assertFalse(lib.review_text_matches("Short wait and a clear explanation of treatment options.", expected))


class GateTests(unittest.TestCase):
    def test_profile_paths_and_aliases(self) -> None:
        slug = "jonah-dimitriou-c4ce067c"
        self.assertTrue(lib.profile_visited(traj(step(f"/doctor/{slug}-overview")), slug))
        self.assertTrue(lib.profile_visited(traj(step(f"/doctor/{slug}-reviews")), slug))
        self.assertFalse(lib.profile_visited(traj(step(f"/doctor/{slug}/bookappointment")), slug))
        self.assertFalse(lib.profile_visited(traj(step("/doctor/timothy-dimitriou-00000000-overview")), slug))
        self.assertTrue(lib.profile_visited_with(traj(step(f"/doctor/{slug}-overview?rpage=2")), slug, rpage="2"))
        self.assertFalse(lib.profile_visited_with(traj(step(f"/doctor/{slug}-overview")), slug, rpage="2"))

    def test_results_params(self) -> None:
        t = traj(step("/results?q=Dermatologists&loc=Newark%2C+DE+19711&gender=f&newpatient=true&insuranceid=4"))
        self.assertTrue(lib.results_visited(t, q=r"dermatolog", gender="f", newpatient=True, insuranceid="4", loc=lib.NEWARK))
        self.assertFalse(lib.results_visited(t, q=r"dermatolog", medicaid=True))
        self.assertFalse(lib.results_visited(t, q=r"psychiatr"))
        self.assertTrue(lib.results_visited(traj(step("/results?sids=1")), sids=("1", "9")))
        self.assertTrue(lib.results_visited(traj(step("/results?q=Dermatologist+Blue+Cross")), q=r"(?=.*dermatolog)(?=.*blue cross)"))

    def test_newark_rule(self) -> None:
        for url in ("/results?q=x", "/results?q=x&loc=19711", "/results?q=x&loc=Newark%2C+DE+19711", "/results?q=x&loc=newark", "/results?q=x&loc=Newark%2C+Delaware", "/results?q=x&zc=19711"):
            self.assertTrue(lib.results_visited(traj(step(url)), loc=lib.NEWARK), url)
        for url in ("/results?q=x&loc=Wilmington%2C+DE", "/results?q=x&loc=Newark%2C+NJ", "/results?q=x&city=Baltimore&state=MD", "/results?q=x&zc=19801"):
            self.assertFalse(lib.results_visited(traj(step(url)), loc=lib.NEWARK), url)

    def test_absent_parameter_rule(self) -> None:
        path = "/choice-awards/awardrecipients"
        self.assertTrue(lib.results_visited(traj(step(path)), path=path, **{"award-class": ("patient", "")}))
        self.assertTrue(lib.results_visited(traj(step(path + "?award-class=patient&page=2")), path=path, **{"award-class": ("patient", "")}))
        self.assertFalse(lib.results_visited(traj(step(path + "?award-class=elite")), path=path, **{"award-class": ("patient", "")}))

    def test_paths_in_order_with_regex(self) -> None:
        slug = "adrian-navarro-b338ac81"
        ordered = traj(step("/login"), step("/account/saved"), step(f"/doctor/{slug}-overview"))
        reversed_ = traj(step("/login"), step(f"/doctor/{slug}-overview"), step("/account/saved"))
        requirements = [("/login", {}), ("/account/saved", {}), (lib.profile_path_pattern(slug), {})]
        self.assertTrue(lib.check_paths_in_order(lib.Judge("t"), ordered, "order", requirements))
        self.assertFalse(lib.check_paths_in_order(lib.Judge("t"), reversed_, "order", requirements))

    def test_signup_email_only_from_signup_steps(self) -> None:
        t = traj(step("/login", "input", "alice.j@test.com"), step("/signup", "input", "new.user@example.com"), step("/signup", "input", "Secret123!"))
        self.assertEqual(lib.signup_email(t), "new.user@example.com")
        self.assertEqual(lib.trajectory_last_email(t), "new.user@example.com")
        self.assertEqual(lib.signup_email(traj(step("/login", "input", "alice.j@test.com"))), "")

    def test_site_urls_accept_any_loopback_port(self) -> None:
        self.assertTrue(lib.is_site_url("http://localhost:40024/results"))
        self.assertTrue(lib.is_site_url("http://127.0.0.1:41024/"))
        self.assertFalse(lib.is_site_url("https://doctor.webmd.com/results"))


class SnapshotContractTests(unittest.TestCase):
    def test_seed_copies_validate_and_tamper_is_rejected(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = str(State().write(root / "initial.db"))
            after = str(State().write(root / "after.db"))
            lib._validate_snapshot_contract(initial, after)  # no exception
            bad = State()
            bad.extra_sql.append("DELETE FROM specialties WHERE id = 10")
            with self.assertRaises(ValueError):
                lib._validate_snapshot_contract(initial, str(bad.write(root / "bad.db")))
            self.assertEqual(lib.table_delta(initial, after, "saved_providers"), {"added": [], "removed": [], "changed": []})
            changed = State()
            changed.add_saved(2, 163)
            delta = lib.table_delta(initial, str(changed.write(root / "changed.db")), "saved_providers")
            self.assertEqual(len(delta["added"]), 1)
            self.assertEqual(lib.saved_delta(initial, str(root / "changed.db"), 2), ({163}, set()))
            self.assertEqual([row["doctor_id"] for row in lib.new_table_rows(initial, str(root / "changed.db"), "saved_providers")], [163])

    def test_ground_truth_derives_every_task_from_the_seed(self) -> None:
        import tempfile

        import ground_truth

        with tempfile.TemporaryDirectory() as directory:
            seed = str(State().write(Path(directory) / "seed.db"))
            facts = ground_truth.all_ground_truth(seed)
            self.assertEqual(sorted(facts), list(range(20)))
            self.assertEqual(facts[17]["location_id"], 32)
            self.assertEqual(facts[13]["earlier"]["slug"], "emerson-huang-f6afead5")
            self.assertEqual(facts[11]["target"]["slug"], "sean-blackwood-45e84c50")


if __name__ == "__main__":
    unittest.main()
