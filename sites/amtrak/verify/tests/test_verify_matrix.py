"""Offline validation matrix for every Amtrak verifier (no Playwright, no docker, no LLM).

For each task: genuine run -> PASS; no-op, shortcut (no navigation), wrong answer,
other task id, unterminated run, foreign origin, corrupt screenshot, schema change and
collateral database writes -> FAIL on the named check. Stateful tasks additionally cover
state-mismatch (DB unchanged) and over-reaching writes.

Run:  python -m pytest sites/amtrak/verify/tests -q     (or python -m unittest discover -s sites/amtrak/verify/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ALICE, Snapshot, VerifierTestCase, login_steps, new_booking_sql, preferred_station_sql, step  # noqa: E402

RESULTS = "/booking/results?trip_type=one-way&origin={o}&destination={d}&departure_date={dt}&passengers={p}&fare_class={f}&time_window=&sort={s}"


def results(o, d, dt, p=1, f="saver", s="price", extra=""):
    return RESULTS.format(o=o, d=d, dt=dt, p=p, f=f, s=s) + extra


# (task, genuine steps, correct answer, [(wrong answer, failing check), ...], shortcut failing check)
CASES = {
    0: (
        [step("/booking/search", "input", "NYP"), step("/booking/search", "click"),
         step(results("NYP", "WAS", "2026-04-20", s="duration"), "done")],
        "Fastest direct service: Acela Express train 2151, 2h 50m.",
        [("Fastest direct service: Carolinian train 79, 3h 12m.", "answer_names_route"),
         ("Acela Express train 2152, 2h 50m.", "answer_has_train_number"),
         ("Acela Express train 2151, 2h 56m.", "answer_has_travel_time")],
        "visited_results_nyp_was_0420_sorted_by_duration",
    ),
    1: (
        [step("/booking/search", "click"), step(results("NYP", "WAS", "2026-04-20", s="price"), "done")],
        "Cheapest: Northeast Regional, starting fare $26.88.",
        [("Cheapest: Carolinian, $26.95.", "answer_names_route"), ("Northeast Regional, $26.95.", "answer_has_starting_fare")],
        "visited_results_nyp_was_0420_price_with_transfers",
    ),
    2: (
        [step("/booking/search", "click"),
         step("/booking/results?trip_type=round-trip&origin=WAS&destination=PHL&departure_date=2026-04-20&return_date=2026-04-22&passengers=1&fare_class=saver&time_window=&sort=duration", "click"),
         step("/booking/results?trip_type=round-trip&origin=WAS&destination=PHL&departure_date=2026-04-20&return_date=2026-04-22&passengers=1&fare_class=saver&time_window=&sort=duration&direct_only=0&leg=return", "click"),
         step("/booking/select-trip", "click"), step("/booking/select-fare", "done")],
        "Business per traveler: $124.83.",
        [("Business per traveler: $90.86.", "answer_has_business_fare")],
        "round_trip_workflow_in_order",
    ),
    3: (
        [step("/booking/multi-city", "input", "SEA"), step("/booking/multi-city", "click"), step("/booking/multi-city", "click"),
         step("/booking/select-trip", "click"), step("/booking/select-fare", "done")],
        "Value per traveler for the full itinerary: $169.65.",
        [("Value per traveler: $147.51.", "answer_has_value_fare")],
        "multi_city_workflow_in_order",
    ),
    4: (
        [step("/booking/search", "click"), step(results("SEA", "LAX", "2026-04-22", p=2), "click"),
         step("/booking/select-trip", "click"), step("/booking/select-fare", "click"), step("/booking/rooms", "done")],
        "The Roomette adds the smallest extra cost: +$316.00.",
        [("The Bedroom adds the smallest extra cost: +$592.00.", "answer_names_room_type"), ("Roomette, +$220.00.", "answer_has_extra_cost")],
        "visited_results_sea_lax_0422_two_passengers",
    ),
    5: (
        login_steps() + [step("/account", "navigate"), step("/account/trips", "done")],
        "ALJDAM, origin CHI, departing Apr 20, 2026.",
        [("ALGX87, origin NYP, departing Apr 20, 2026.", "answer_has_booking_code"), ("ALJDAM, origin DEN, Apr 20, 2026", "answer_has_origin_code"),
         ("ALJDAM, CHI, Apr 22, 2026", "answer_has_departure_date")],
        "visited_login_page",
    ),
    6: (
        [step("/trip-lookup", "input", "ALGX87"), step("/trip-lookup", "input", ALICE), step("/trip-lookup", "click"), step("/trip/ALGX87", "done")],
        "Route: Acela Express, departing 2026-04-20.",
        [("Route: Northeast Regional, departing 2026-04-20.", "answer_names_route"), ("Acela Express, Apr 16, 2026", "answer_has_departure_date")],
        "visited_trip_lookup",
    ),
    7: (
        login_steps() + [step("/account", "navigate"), step("/account/rewards", "done")],
        "Points balance: 4,786 points.",
        [("Points balance: 2400 points.", "answer_has_points_balance")],
        "visited_login_page",
    ),
    8: (
        login_steps() + [step("/account", "navigate"), step("/account/edit", "input", "SEA"), step("/account/edit", "click"),
                         step("/account", "navigate"), step("/account/rewards", "done")],
        "Preferred station: SEA.",
        [("Preferred station: NYP.", "answer_has_station_code")],
        "visited_login_page",
    ),
    9: (
        [step("/routes", "click"), step("/routes/amtrak-cascades", "done")],
        "Stops in order: VAN, SEA, PDX, EUG.",
        [("Stops in order: VAC, SEA, PDX, EUG.", "answer_lists_stops_in_order"), ("SEA, VAN, PDX, EUG", "answer_lists_stops_in_order")],
        "visited_cascades_route_page",
    ),
    10: (
        [step("/service-alerts", "done")],
        "Next step: Review the fare page before booking if you need a sleeper on a tighter schedule.",
        [("Next step: Filter for direct service if you want to avoid the transfer pattern.", "answer_has_next_step")],
        "visited_service_alerts",
    ),
    11: (
        [step("/service-alerts", "done")],
        "Westbound long-distance departures board from track 3 (instead of track 2).",
        [("They board from track 2.", "answer_has_boarding_track"), ("Not track 3, the advisory says track 2.", "answer_has_boarding_track"),
         ("Westbound departures use track 2 instead of track 3.", "answer_has_boarding_track")],
        "visited_service_alerts",
    ),
    12: (
        [step("/booking/search", "click"), step(results("CHI", "DEN", "2026-04-20", f="flexible"), "done")],
        "California Zephyr, Flexible price $96.56.",
        [("California Zephyr, $72.06.", "answer_has_flexible_price"), ("Southwest Chief, $96.56.", "answer_names_route")],
        "visited_results_chi_den_0420",
    ),
    13: (
        [step("/booking/search", "click"), step(results("SAC", "SJC", "2026-04-16"), "done")],
        "Capitol Corridor, starting fare $37.22.",
        [("Capitol Corridor, $42.80.", "answer_has_starting_fare"), ("Coast Starlight, $37.22.", "answer_names_route")],
        "visited_results_sac_sjc_0416_saver",
    ),
    14: (
        [step("/stations", "click"), step("/stations/ANA", "navigate"), step("/stations/SBA", "done")],
        "Santa Barbara (SBA) supports checked baggage; Anaheim (ANA) is carry-on only.",
        [("Anaheim (ANA) supports checked baggage.", "answer_names_checked_baggage_station"),
         ("Santa Barbara does not support checked baggage; Anaheim does.", "answer_names_checked_baggage_station"),
         ("Anaheim (ANA) supports checked baggage; Santa Barbara (SBA) is carry-on only.", "answer_names_checked_baggage_station"),
         ("Both Anaheim and Santa Barbara support checked baggage.", "answer_names_checked_baggage_station"),
         ("Neither station supports checked baggage.", "answer_names_checked_baggage_station")],
        "visited_station_ANA",
    ),
    15: (
        [step("/help", "input", "checked baggage"), step("/help?q=checked+baggage", "click"), step("/help/checked-baggage-timing", "done")],
        "Checked baggage closes 45 minutes before departure; it applies to long-distance departures at staffed stations.",
        [("Checked baggage closes 30 minutes before departure; long-distance departures.", "answer_has_cutoff_minutes"),
         ("45 minutes before departure for all trains.", "answer_names_departure_kind")],
        "visited_checked_baggage_timing_article",
    ),
    16: (
        [step("/help", "input", "refund"), step("/help?q=refund", "click"), step("/help/refunds-and-credits", "done")],
        'Title: "Refund language used in the mirror", category: Refunds.',
        [('Title: "Carry-on and checked baggage basics", category: Baggage.', "answer_has_exact_title"),
         ("Refund language used in the mirror, category: Trips.", "answer_has_category")],
        "performed_refund_search",
    ),
    17: (
        login_steps() + [step("/account", "navigate"), step("/booking/search", "click"), step(results("NYP", "WAS", "2026-04-20"), "click"),
                         step("/booking/select-trip", "click"), step("/booking/select-fare", "click"), step("/booking/passengers", "input", "Alice"),
                         step("/booking/passengers", "click"), step("/booking/review", "click"), step("/booking/checkout", "click"),
                         step("/booking/confirmation?code=ZSLYNG", "done")],
        "New booking code: ZSLYNG.",
        [("New booking code: ALGX87.", "answer_has_new_booking_code")],
        "visited_login_page",
    ),
}
STATEFUL_AFTER = {8: preferred_station_sql("SEA"), 17: new_booking_sql("ZSLYNG")}


class MatrixTests(VerifierTestCase):
    """Runs the common matrix against every verifier."""

    def genuine_after(self, n: int) -> Snapshot:
        return Snapshot(STATEFUL_AFTER.get(n))

    def test_genuine_runs_pass(self) -> None:
        for n, (steps, answer, _wrong, _gate) in CASES.items():
            with self.subTest(task=n):
                self.N = n
                self.assertPasses(self.verdict(steps, answer, after=self.genuine_after(n)))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        for n in (0, 8, 17):
            with self.subTest(task=n):
                self.N = n
                steps, answer, _w, _g = CASES[n]
                self.assertPasses(self.verdict(steps, answer, after=self.genuine_after(n), snapshots_in_run_dir=True))

    def test_noop_runs_fail_on_empty_answer(self) -> None:
        for n in CASES:
            with self.subTest(task=n):
                self.N = n
                self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_shortcut_runs_fail_on_navigation_gate(self) -> None:
        for n, (_steps, answer, _wrong, gate) in CASES.items():
            with self.subTest(task=n):
                self.N = n
                self.assertFailsOn(self.verdict([step("/"), step("/", "done")], answer), gate)

    def test_wrong_answers_fail(self) -> None:
        for n, (steps, _answer, wrong, _gate) in CASES.items():
            for wrong_answer, check in wrong:
                with self.subTest(task=n, answer=wrong_answer):
                    self.N = n
                    self.assertFailsOn(self.verdict(steps, wrong_answer, after=self.genuine_after(n)), check)

    def test_other_task_id_fails(self) -> None:
        for n in (0, 8, 17):
            with self.subTest(task=n):
                self.N = n
                steps, answer, _w, _g = CASES[n]
                self.assertFailsOn(self.verdict(steps, answer, after=self.genuine_after(n), task_id="Amtrak--99"), "trajectory_task_matches")

    def test_unterminated_foreign_origin_and_corrupt_screenshot_fail(self) -> None:
        self.N = 9
        steps, answer, _w, _g = CASES[9]
        self.assertFailsOn(self.verdict(steps, answer, trajectory_updates={"terminated": False}), "trajectory_completed")
        self.assertFailsOn(self.verdict(steps, answer, trajectory_updates={"start_url": "http://127.0.0.1:41024/"}), "all_urls_match_local_origin")
        self.assertFailsOn(self.verdict(steps, answer, corrupt_screenshot=True), "screenshots_decode")
        foreign = [step("/routes", "click"), step("https://www.amtrak.com/routes/cascades", "navigate"), step("/routes/amtrak-cascades", "done")]
        self.assertFailsOn(self.verdict(foreign, answer), "all_urls_match_local_origin")

    def test_read_only_tasks_reject_collateral_writes(self) -> None:
        for n, table_sql, check in [
            (0, "UPDATE users SET phone='000' WHERE email='alice.j@test.com'", "read_only_users_unchanged"),
            (6, "UPDATE bookings SET status='Cancelled' WHERE booking_code='ALGX87'", "read_only_bookings_unchanged"),
            (7, "UPDATE reward_accounts SET points_balance=points_balance+1", "read_only_reward_accounts_unchanged"),
        ]:
            with self.subTest(task=n):
                self.N = n
                steps, answer, _w, _g = CASES[n]
                self.assertFailsOn(self.verdict(steps, answer, after=Snapshot([table_sql])), check)

    def test_answer_phrasing_variants_pass(self) -> None:
        variants = {
            14: ["SBA", "Santa Barbara, not Anaheim, supports checked baggage.", "Anaheim does not support checked baggage; Santa Barbara does.",
                 "Anaheim (ANA) is carry-on only and Santa Barbara (SBA) offers checked baggage.", "The answer is SBA, since ANA has no checked baggage."],
            11: ["Track 3", "They now board from track #3 rather than track 2.", "track number 3"],
            0: ["Acela Express 2151, 2 hours 50 minutes", "Acela Express (train 2151) takes 2:50", "Acela Express #2151 - 2h 46m"],
            5: ["ALJDAM / CHI / 2026-04-20", "Booking ALJDAM departs from CHI on April 20, 2026"],
            7: ["4,786", "Alice has 4786 points"],
        }
        for n, answers in variants.items():
            steps, _answer, _w, _g = CASES[n]
            for answer in answers:
                with self.subTest(task=n, answer=answer):
                    self.N = n
                    self.assertPasses(self.verdict(steps, answer, after=self.genuine_after(n)))

    def test_search_logs_writes_are_rejected_for_read_only_tasks(self) -> None:
        """/search, /help?q= and /booking/results no longer commit a SearchLog row, so a
        row appearing in the after-state means a GET route started writing again."""
        insert = ("INSERT INTO search_logs(id,user_id,query,category,result_count,created_at) "
                  "VALUES (1,NULL,'baggage','global',4,'2026-04-18 08:00:00')")
        for n in (0, 10, 16):
            with self.subTest(task=n):
                self.N = n
                steps, answer, _w, _g = CASES[n]
                self.assertFailsOn(self.verdict(steps, answer, after=Snapshot([insert])),
                                   "read_only_search_logs_unchanged")

    def test_search_logs_writes_are_rejected_for_stateful_tasks(self) -> None:
        insert = ("INSERT INTO search_logs(id,user_id,query,category,result_count,created_at) "
                  "VALUES (1,NULL,'nyp was','booking',13,'2026-04-18 08:00:00')")
        for n, extra in ((8, preferred_station_sql("SEA")), (17, new_booking_sql("ZSLYNG"))):
            with self.subTest(task=n):
                self.N = n
                steps, answer, _w, _g = CASES[n]
                self.assertFailsOn(self.verdict(steps, answer, after=Snapshot(extra + [insert])),
                                   "search_logs_unchanged")

    def test_tiny_screenshots_are_rejected(self) -> None:
        """A decodable 1x1 PNG used to satisfy the screenshot check; it no longer does."""
        self.N = 9
        steps, answer, _w, _g = CASES[9]
        self.assertFailsOn(self.verdict(steps, answer, tiny_screenshots=True), "screenshots_decode")

    def test_snapshot_contract_fails_closed(self) -> None:
        self.N = 0
        steps, answer, _w, _g = CASES[0]
        self.assertFailsOn(self.verdict(steps, answer, after=Snapshot(["CREATE TABLE injected(id INTEGER PRIMARY KEY)"])), "snapshot_contract_invalid")
        self.assertFailsOn(self.verdict(steps, answer, after=Snapshot(["UPDATE routes SET name='tampered' WHERE slug='acela-express'"])), "snapshot_contract_invalid")
        self.assertFailsOn(self.verdict(steps, answer, initial=Snapshot(["DELETE FROM bookings WHERE id=60"])), "snapshot_contract_invalid")

    # ------------------------------------------------------------------ stateful specifics
    def test_task_8_state_mismatch_and_overreach(self) -> None:
        self.N = 8
        steps, answer, _w, _g = CASES[8]
        self.assertFailsOn(self.verdict(steps, answer), "user_preferred_station_updated")
        only_user = Snapshot(preferred_station_sql("SEA")[:1])
        self.assertFailsOn(self.verdict(steps, answer, after=only_user), "reward_preferred_station_updated")
        overreach = Snapshot(preferred_station_sql("SEA") + ["UPDATE users SET phone='000' WHERE email='alice.j@test.com'"])
        self.assertFailsOn(self.verdict(steps, answer, after=overreach), "user_row_changed_only_preferred_station")
        others = Snapshot(preferred_station_sql("SEA") + ["UPDATE users SET preferred_station_code='SEA' WHERE email='bob.c@test.com'"])
        self.assertFailsOn(self.verdict(steps, answer, after=others), "other_users_unchanged")
        wrong_order = login_steps() + [step("/account/rewards", "navigate"), step("/account/edit", "click"), step("/account", "done")]
        self.assertFailsOn(self.verdict(wrong_order, answer, after=self.genuine_after(8)), "edit_then_rewards_in_order")

    def test_task_17_state_mismatch_and_wrong_booking(self) -> None:
        self.N = 17
        steps, answer, _w, _g = CASES[17]
        self.assertFailsOn(self.verdict(steps, answer), "exactly_one_new_booking")
        coach = Snapshot(new_booking_sql("ZSLYNG", fare="Value", accommodation="Coach Seat"))
        self.assertFailsOn(self.verdict(steps, answer, after=coach), "single_direct_business_segment")
        no_points = Snapshot(new_booking_sql("ZSLYNG", credit_points=False))
        self.assertFailsOn(self.verdict(steps, answer, after=no_points), "reward_points_credited")
        mismatch = Snapshot(new_booking_sql("ZSLYNG"))
        self.assertFailsOn(self.verdict(steps, "New booking code: ZSLYNH.", after=mismatch), "answer_has_new_booking_code")
        missing_fare_page = login_steps() + [step("/booking/search", "click"), step(results("NYP", "WAS", "2026-04-20"), "click"),
                                             step("/booking/select-trip", "click"), step("/booking/passengers", "click"), step("/booking/review", "click"),
                                             step("/booking/checkout", "click"), step("/booking/confirmation", "done")]
        self.assertFailsOn(self.verdict(missing_fare_page, answer, after=mismatch), "checkout_workflow_in_order")


if __name__ == "__main__":
    unittest.main()
