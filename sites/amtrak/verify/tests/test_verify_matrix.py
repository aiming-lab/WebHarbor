"""V2 grading regression: synthetic controls, never browser-completion claims."""

from __future__ import annotations
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support import Snapshot, write_run, step, new_booking_sql, preferred_station_sql
from contract import expected_answer, run_checks
from answer_contract import equivalent, parse_answer
from verify_lib import Judge, load_run, _validate_snapshot_contract

BASE = "http://localhost:41024"


def search(
    o,
    d,
    day="2026-04-20",
    fare="saver",
    sort="price",
    passengers=1,
    trip_type="one-way",
    extra="",
):
    return f"/booking/results?origin={o}&destination={d}&departure_date={day}&fare_class={fare}&sort={sort}&passengers={passengers}&trip_type={trip_type}{extra}"


FARE = ["/booking/select-trip", "/booking/select-fare"]
PATHS = {
    0: [search("NYP", "WAS", sort="duration")],
    1: [search("NYP", "WAS")],
    2: [
        search(
            "WAS",
            "PHL",
            sort="duration",
            trip_type="round-trip",
            extra="&return_date=2026-04-22",
        ),
        search("WAS", "PHL", extra="&leg=return"),
    ]
    + FARE,
    3: ["/booking/multi-city"] + FARE,
    4: [search("SEA", "LAX", "2026-04-22", passengers=2)] + FARE + ["/booking/rooms"],
    5: [
        "/login",
        "/account/trips",
        "/trip/ALJDAM",
        search("CHI", "DEN", fare="flexible"),
    ]
    + FARE,
    6: ["/trip-lookup", "/trip/ALGX87", search("NYP", "WAS", sort="duration")] + FARE,
    7: ["/login", "/account/rewards", "/logout", "/login", "/account/rewards"],
    8: ["/login", "/account/edit", "/account/rewards"],
    9: ["/routes/amtrak-cascades"]
    + ["/stations/" + c for c in ["VAN", "SEA", "PDX", "EUG"]],
    10: ["/service-alerts", search("SEA", "LAX", "2026-04-22", passengers=2)]
    + FARE
    + ["/booking/rooms"],
    11: [
        "/service-alerts",
        "/schedules?station_code=DEN&date=2026-04-20",
        "/stations/DEN",
    ],
    12: [search("CHI", "DEN", fare="flexible")],
    13: [search("SAC", "SJC", "2026-04-16", fare=f) for f in ["saver", "flexible"]],
    14: [
        "/stations/ANA",
        "/stations/SBA",
        "/routes/pacific-surfliner",
        "/help/checked-baggage-timing",
    ],
    15: ["/help/checked-baggage-timing", search("CHI", "DEN")],
    16: [
        "/help?q=refund",
        "/help/refunds-and-credits",
        search("NYP", "WAS", sort="duration"),
    ]
    + FARE,
    17: ["/login", search("NYP", "WAS")]
    + FARE
    + [
        "/booking/passengers",
        "/booking/review",
        "/booking/checkout",
        "/booking/confirmation",
    ],
}
MUTATIONS = {
    "profile": "UPDATE users SET first_name='Unrequested' WHERE id=1",
    "tier": "UPDATE reward_accounts SET tier='Unexpected' WHERE id=1",
    "ticket_trip": "UPDATE tickets SET trip_id=1 WHERE booking_id=61",
    "ticket_passenger": "UPDATE tickets SET passenger_id=1 WHERE booking_id=61",
    "passenger_owner": "UPDATE passengers SET user_id=2 WHERE booking_id=61",
    "reward_owner": "UPDATE reward_activities SET reward_account_id=2 WHERE id=61",
    "reward_amount": "UPDATE reward_activities SET points_delta=1 WHERE id=61",
    "empty_name": "UPDATE passengers SET first_name='',last_name='' WHERE booking_id=61",
    "segment_date": "UPDATE booking_segments SET depart_dt='2026-04-25 12:00:00' WHERE booking_id=61",
    "payment": "UPDATE payment_mocks SET amount=.01 WHERE booking_id=61",
}


class Contracts(unittest.TestCase):
    def build(self, n, root):
        initial = Snapshot().write(root / "initial.db")
        sql = (
            preferred_station_sql("SEA")
            if n == 8
            else new_booking_sql() if n == 17 else []
        )
        after = Snapshot(sql).write(root / "after.db")
        answer = expected_answer(n, str(initial), str(after))
        paths = PATHS[n]
        steps = []
        logins = 0
        for path in paths:
            item = step(path)
            item["observed_text"] = (
                "Synthetic control content: Coast Starlight Denver California Zephyr Washington → Philadelphia Philadelphia → Washington Seattle → Portland Portland → Sacramento Sacramento → Los Angeles Apr 18, 2026 Apr 20, 2026 Apr 22, 2026 Apr 23, 2026"
            )
            if path == "/login":
                email = "bob.c@test.com" if n == 7 and logins else "alice.j@test.com"
                item.update(action="input", params={"text": email})
                logins += 1
            if path == "/account/rewards":
                item["observed_text"] += (
                    " AGR-47137" if n == 7 and logins == 2 else " AGR-47000"
                )
            steps.append(item)
        write_run(root, f"Amtrak--{n}", steps, json.dumps(answer))
        return initial, after, load_run(root)

    def grade(self, n, initial, after, tr):
        judge = Judge(f"Amtrak--{n}")
        run_checks(n, judge, tr, str(initial), str(after))
        return judge

    def test_all_tasks_and_negative_package_controls(self):
        for n in range(18):
            with self.subTest(task=n), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                initial, after, tr = self.build(n, root)
                _validate_snapshot_contract(str(initial), str(after))
                self.assertTrue(self.grade(n, initial, after, tr).passed)
                for kind in [
                    "empty",
                    "homepage",
                    "unterminated",
                    "foreign",
                    "no_observation",
                    "wrong_id",
                    "extra_key",
                ]:
                    with self.subTest(task=n, control=kind):
                        bad = copy.deepcopy(tr)
                        if kind == "empty":
                            bad["final_answer"] = ""
                        if kind == "homepage":
                            for s in bad["steps"]:
                                s["url"] = BASE + "/"
                        if kind == "unterminated":
                            bad["terminated"] = False
                        if kind == "foreign":
                            bad["steps"][0]["url"] = "https://example.com/"
                        if kind == "no_observation":
                            for s in bad["steps"]:
                                s["observed_text"] = ""
                        if kind == "wrong_id":
                            bad["task_id"] = "Amtrak--999"
                        if kind == "extra_key":
                            obj = json.loads(bad["final_answer"])
                            obj["reference"] = "extra"
                            bad["final_answer"] = json.dumps(obj)
                        self.assertFalse(self.grade(n, initial, after, bad).passed)
                for key in json.loads(tr["final_answer"]):
                    bad = copy.deepcopy(tr)
                    obj = json.loads(bad["final_answer"])
                    obj[key] = "wrong reference " + str(obj[key])
                    bad["final_answer"] = json.dumps(obj)
                    with self.subTest(task=n, wrong_field=key):
                        self.assertFalse(self.grade(n, initial, after, bad).passed)

    def test_checkout_precise_deltas(self):
        for name, sql in MUTATIONS.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                initial, after, tr = self.build(17, Path(td))
                with sqlite3.connect(after) as db:
                    db.execute(sql)
                self.assertFalse(self.grade(17, initial, after, tr).passed)

    def test_forged_total_with_matching_payment(self):
        with tempfile.TemporaryDirectory() as td:
            initial, after, tr = self.build(17, Path(td))
            with sqlite3.connect(after) as db:
                db.execute("UPDATE bookings SET total_amount=.01 WHERE id=61")
                db.execute("UPDATE payment_mocks SET amount=.01 WHERE booking_id=61")
            self.assertFalse(self.grade(17, initial, after, tr).passed)

    def test_readonly_collateral_write(self):
        for n in set(range(18)) - {8, 17}:
            with self.subTest(task=n), tempfile.TemporaryDirectory() as td:
                initial, after, tr = self.build(n, Path(td))
                with sqlite3.connect(after) as db:
                    db.execute("UPDATE users SET first_name='Other' WHERE id=2")
                self.assertFalse(self.grade(n, initial, after, tr).passed)

    def test_profile_collateral_and_noop(self):
        for sql in [None, "UPDATE users SET first_name='Other' WHERE id=1"]:
            with self.subTest(sql=sql), tempfile.TemporaryDirectory() as td:
                initial, after, tr = self.build(8, Path(td))
                with sqlite3.connect(after) as db:
                    db.execute(
                        sql
                        or "UPDATE users SET preferred_station_code='NYP' WHERE id=1"
                    )
                self.assertFalse(self.grade(8, initial, after, tr).passed)

    def test_fixture_tamper_even_both_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            initial, after, tr = self.build(0, Path(td))
            for p in [initial, after]:
                with sqlite3.connect(p) as db:
                    db.execute("UPDATE fare_options SET multiplier=999 WHERE id=1")
            with self.assertRaisesRegex(ValueError, "immutable fixture"):
                _validate_snapshot_contract(str(initial), str(after))

    def test_answer_equivalents_and_semantic_negatives(self):
        for a, b in [
            ("4,786", 4786),
            ("four thousand seven hundred eighty-six", 4786),
            ("$26.88", 26.88),
            ("April 20, 2026", "2026-04-20"),
            ("2:00 PM", "14:00"),
            ("ROOMETTE.", "Roomette"),
        ]:
            with self.subTest(value=a):
                self.assertTrue(equivalent(a, b))
        for a, b in [
            ("Reference 4786", 4786),
            ("not Roomette", "Roomette"),
            (True, 1),
            ("false", False),
            (["VAN", "SEA", "CHI", "PDX", "EUG"], ["VAN", "SEA", "PDX", "EUG"]),
            ("1 point; reference 4786", 4786),
            ("one two", 3),
            ("one hundred hundred", 10000),
            ("and three", 3),
            ("twenty twenty", 40),
            ("one thousand and", 1000),
        ]:
            with self.subTest(value=a):
                self.assertFalse(equivalent(a, b))

    def test_reject_duplicate_and_nonfinite_json(self):
        for raw in ['{"a":1,"a":2}', '{"a":NaN}', "[]", '{"a":1} trailing']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_answer(raw)

    def test_corrupt_and_tiny_screenshots(self):
        from PIL import Image

        for mode in ["corrupt", "tiny"]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                initial, after, tr = self.build(0, Path(td))
                shot = Path(td) / "screenshots/step_000.png"
                if mode == "corrupt":
                    shot.write_bytes(b"broken")
                else:
                    Image.new("RGB", (1, 1)).save(shot)
                self.assertFalse(self.grade(0, initial, after, tr).passed)


if __name__ == "__main__":
    unittest.main()
