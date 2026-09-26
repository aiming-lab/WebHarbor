"""Shared fixtures for the qatar_airways verifier tests (reviewer contract).

Snapshots are copies of the real deterministic seed (instance_seed/
qatar_airways.db, built at image time with PYTHONHASHSEED=0) with the
stateful-task mutations applied through sqlite, and trajectories are
hand-written in the agent_demo/agent.py shape. No LLM.

The seed DB resolves from the review container (wh-qa-review); the
QA_TEST_SEED_DB env var overrides the location. Run with plain python3 +
pytest:

    python3 -m pytest sites/qatar_airways/verify/tests -q
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
REPO_ROOT = SITE_DIR.parent.parent
BASE = "http://127.0.0.1:47089"
PASSWORD = "TestPass123!"
CONTAINER = "wh-qa-review"
CACHE = Path(tempfile.gettempdir()) / "qa_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("QA_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp",
                        f"{CONTAINER}:/opt/WebSyn/qatar_airways/instance_seed/qatar_airways.db",
                        str(CACHE)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot acquire the seed DB (docker cp failed): {r.stderr[:200]}")
    return CACHE


# ------------------------------------------------------------------ tiny valid PNG
def tiny_png(width: int = 4, height: int = 4) -> bytes:
    raw = b"".join(b"\x00" + b"\x40\x90\xd0" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (len(data).to_bytes(4, "big") + tag + data
                + zlib.crc32(tag + data).to_bytes(4, "big"))

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = tiny_png()


# ------------------------------------------------------------------ run-dir builder
class RunBuilder:
    """Hand-writes an agent_demo-shaped run directory: trajectory.json + screenshots/."""

    def __init__(self, root: Path, task_id: str, start_path: str = "/"):
        self.root = root
        self.shots_dir = root / "screenshots"
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        (self.shots_dir / "step_000.png").write_bytes(PNG)
        self.steps: list[dict[str, Any]] = []
        self.task_id = task_id
        self.start_url = BASE + start_path
        self.final_answer: str | None = None
        self.final_path = start_path

    def step(self, path: str, action: str = "click", params: dict | None = None,
             url_after: str | None = None, url: str | None = None):
        i = len(self.steps)
        before = f"step_{i:03d}.png"
        after = f"step_{i + 1:03d}.png"
        (self.shots_dir / after).write_bytes(PNG)
        self.steps.append({
            "step": i,
            "url": (url if url is not None else (BASE + path if path.startswith("/") else path)),
            "title": "Qatar Airways",
            "thought": f"review fixture step on {path}",
            "action": action,
            "params": params or {},
            "observed_text": "fixture",
            "observed_text_before": "fixture",
            "screenshot_before": before,
            "screenshot_after": after,
            "screenshot": after,
            **({"url_after": (BASE + url_after if url_after and url_after.startswith("/")
                             else url_after)} if url_after else {}),
        })
        self.final_path = path
        return self

    def fill(self, path: str, text: str, selector: str = "input"):
        return self.step(path, "fill", {"text": text, "selector": selector})

    def login(self, email: str, password: str = PASSWORD):
        return (self.fill("/en/Privilege-Club/login.html", email, "input[name=email]")
                    .fill("/en/Privilege-Club/login.html", password, "input[name=password]")
                    .step("/en/Privilege-Club/login.html", "click",
                          {"selector": "button[type=submit]"},
                          url_after="/en/Privilege-Club/dashboard.html"))

    def done(self, answer: str, final_path: str | None = None, terminated: bool = True,
             reason: str = "agent_done", task_id: str | None = None):
        self.final_answer = answer
        traj = {
            "task": f"{task_id or self.task_id} fixture",
            "task_id": task_id or self.task_id,
            "start_url": self.start_url,
            "model": "fixture",
            "max_steps": 120,
            "steps": self.steps,
            "terminated": terminated,
            "termination_reason": reason,
            "final_answer": answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (final_path or self.final_path),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return traj

    def goto(self, path: str):
        return self.step(path, "goto", {})


def build_run(tmp: Path, name: str, task_id: str, start: str = "/") -> RunBuilder:
    root = tmp / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return RunBuilder(root, task_id, start)


def copy_db(source: Path, dest: Path) -> Path:
    shutil.copy2(source, dest)
    return dest


def mutate_db(source: Path, dest: Path, statements: list[tuple[str, tuple | list]]) -> Path:
    """Copy the seed and apply (sql, params) statements."""
    shutil.copy2(source, dest)
    con = sqlite3.connect(str(dest))
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return dest


def noop_run(tmp: Path, index: int) -> Path:
    """Homepage-only, empty-answer, clean-DB run dir (initial == after == seed)."""
    root = tmp / f"noop_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    seed = _acquire_seed()
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Qatar Airways--{index}")
    b.step("/", "goto", {})
    b.done("", final_path="/")
    return root


def run_verifier(index: int, run_dir: Path) -> dict:
    """Run verify_<index>.py --run_dir <run_dir> under the current interpreter."""
    if not (run_dir / "initial.db").is_file():
        copy_db(_acquire_seed(), run_dir / "initial.db")
    verifier = VERIFY_DIR / f"verify_{index}.py"
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    r = subprocess.run([sys.executable, str(verifier), "--run_dir", str(run_dir)],
                       capture_output=True, text=True, cwd=str(VERIFY_DIR), env=env)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"task_id": f"Qatar Airways--{index}", "pass": False,
                "reason": "verifier_crashed", "stdout": r.stdout[-400:],
                "stderr": r.stderr[-400:]}


def db_one(db_path: Path | str, sql: str, params: tuple = ()) -> Any:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


# ------------------------------------------------------------------ honest fixtures
def honest_booking_statements(pnr: str, *, cabin: str, fare: str, adults: int,
                               total: int, legs: list[tuple], passengers: list[tuple],
                               promo: str | None = None, pc_number: str | None = None,
                               user_id: int | None = None, contact_email: str,
                               contact_last: str, card_last4: str = "4242",
                               avios_redeemed: int = 0) -> list[tuple]:
    """Reproduce the app's booking writes: booking row + legs + passengers."""
    stmts = [("INSERT INTO bookings (pnr, user_id, pc_number, contact_email,"
              " contact_last_name, cabin, fare_type, adults, children, extra_bags,"
              " total_paid, avios_redeemed, promo_code, card_last4, status,"
              " checked_in, created_at) VALUES (?,?,?,?,?,?,?, ?,0,0,?,?,?,?,"
              "'confirmed',0,'2026-09-24')",
              (pnr, user_id, pc_number, contact_email, contact_last, cabin, fare,
               adults, total, avios_redeemed, promo, card_last4))]
    for (number, origin, dest, day, dep, arr, equip, dist, fare_price) in legs:
        stmts.append(("INSERT INTO booking_legs (booking_id, flight_number,"
                      " origin_code, dest_code, leg_date, dep_time, arr_time,"
                      " equipment, distance_km, fare_price, seat_fee, gate)"
                      " VALUES ((SELECT id FROM bookings WHERE pnr=?),?,?,?,?,?,?,?,"
                      " ?,?,0,'B02')",
                      (pnr, number, origin, dest, day, dep, arr, equip, dist, fare_price)))
    for (title, first, last, ptype) in passengers:
        stmts.append(("INSERT INTO passengers (booking_id, title, first_name,"
                      " last_name, pax_type, ticket_number) VALUES"
                      " ((SELECT id FROM bookings WHERE pnr=?),?,?,?,?,'157-0000000001')",
                      (pnr, title, first, last, ptype)))
    return stmts


HONEST = {}


def honest_run(tmp: Path, index: int):
    """The honest navigation + DB state for task `index`; returns (run_dir, answer)."""
    seed = _acquire_seed()
    root = tmp / f"honest_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    b = RunBuilder(root, f"Qatar Airways--{index}")
    after = root / "after.db"
    stmts: list[tuple] = []
    answer = ""

    if index == 0:
        pnr = "AA12CD"
        b.goto("/")
        b.step("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=2"
                "&children=0&cabin=Economy", "goto", {})
        b.step("/en/booking/passenger-details.html?from=DOH&to=LHR&depart=2026-10-08"
               "&adults=2&children=0&cabin=Economy&fare=ECO_LITE&flight=105", "goto", {})
        b.fill("/en/booking/passenger-details.html", "John")
        b.fill("/en/booking/passenger-details.html", "Smith")
        b.step("/en/booking/payment.html", "goto", {})
        b.step(f"/en/booking/confirmation.html?pnr={pnr}", "goto", {})
        stmts = honest_booking_statements(
            pnr, cabin="Economy", fare="ECO_LITE", adults=2, total=1490,
            legs=[(105, "DOH", "LHR", "2026-10-08", "01:05", "07:15", "359", 5215, 1330)],
            passengers=[("Mr", "John", "Smith", "adult"), ("Mrs", "Mary", "Smith", "adult")],
            contact_email="john.smith@example.com", contact_last="Smith",
            card_last4="9010")
        answer = (f"Booked the cheapest Economy Lite flight QR105 for John and Mary "
                  f"Smith. Booking reference {pnr}. Total charged USD 1,490.")

    elif index == 1:
        pnr = "BB34EF"
        b.goto("/")
        b.step("/en/search-results.html?from=DOH&to=BKK&depart=2026-10-12"
               "&ret=2026-10-26&adults=1&children=0&cabin=Economy", "goto", {})
        b.step("/en/booking/select-return.html?from=DOH&to=BKK&depart=2026-10-12"
               "&ret=2026-10-26&adults=1&children=0&cabin=Economy&fare=ECO_CLASSIC"
               "&flight=834", "goto", {})
        b.step("/en/booking/passenger-details.html?from=DOH&to=BKK&depart=2026-10-12"
               "&ret=2026-10-26&ret_flight=837&adults=1&children=0&cabin=Economy"
               "&fare=ECO_CLASSIC&flight=834", "goto", {})
        b.step("/en/booking/payment.html", "goto", {})
        b.step(f"/en/booking/confirmation.html?pnr={pnr}", "goto", {})
        stmts = honest_booking_statements(
            pnr, cabin="Economy", fare="ECO_CLASSIC", adults=1, total=1814,
            legs=[(834, "DOH", "BKK", "2026-10-12", "02:00", "12:10", "77W", 5656, 795),
                  (837, "BKK", "DOH", "2026-10-26", "02:30", "06:20", "77W", 5656, 825)],
            passengers=[("Ms", "Sarah", "Chen", "adult")],
            contact_email="sarah.chen@example.com", contact_last="Chen",
            card_last4="7890")
        answer = (f"Booked the earliest flights: outbound QR834 and return QR837 in "
                  f"Economy Classic. Booking reference {pnr}. Total charged USD 1,814.")

    elif index == 2:
        pnr = "CC56GH"
        b.login("alice.j@test.com")
        b.goto("/en/Privilege-Club/dashboard.html")
        b.goto("/")
        b.step("/en/search-results.html?from=DOH&to=CDG&depart=2026-11-02&adults=1"
               "&children=0&cabin=Business", "goto", {})
        b.step("/en/booking/passenger-details.html?from=DOH&to=CDG&depart=2026-11-02"
               "&adults=1&children=0&cabin=Business&fare=BUS_CLASSIC&flight=41", "goto", {})
        b.fill("/en/booking/passenger-details.html", "QRPC0004217")
        b.step("/en/booking/payment.html", "goto", {})
        b.step(f"/en/booking/confirmation.html?pnr={pnr}", "goto", {})
        b.goto("/en/Privilege-Club/dashboard.html")
        stmts = honest_booking_statements(
            pnr, cabin="Business", fare="BUS_CLASSIC", adults=1, total=8915,
            legs=[(41, "DOH", "CDG", "2026-11-02", "07:45", "13:20", "359", 4974, 7960)],
            passengers=[("Ms", "Alice", "Johnson", "adult")],
            pc_number="QRPC0004217", user_id=1,
            contact_email="alice.j@test.com", contact_last="Johnson",
            card_last4="4242")
        stmts += [
            ("UPDATE users SET avios=49990, qpoints=614 WHERE id=1", ()),
            ("INSERT INTO activities (user_id, kind, avios, qpoints, description,"
             " occurred_at) VALUES (1,'earn',1740,199,'Flight QR041 DOH→CDG"
             " (Business Classic)','2026-09-24')", ()),
        ]
        answer = (f"Booked Business Classic DOH to Paris CDG on QR041 with my "
                  f"Privilege Club number on the booking. Booking reference {pnr}. "
                  f"Total charged USD 8,915. My Avios balance afterwards is 49,990.")

    elif index == 3:
        b.goto("/")
        b.step("/en/flight-status.html?mode=number&number=QR004&date=2026-09-24",
               "goto", {})
        b.step("/en/flight-status.html?mode=route&from=LHR&to=DOH&date=2026-09-24",
               "goto", {})
        b.goto("/en/our-fleet.html")
        b.goto("/en/our-fleet/Airbus-A380-800.html")
        answer = ("QR004 (London to Doha, 24 September 2026) is En route. Scheduled "
                  "departure 15:05, estimated arrival 23:47, operated by the Airbus "
                  "A380-800, which offers First, Business and Economy cabins and "
                  "seats 517 passengers. The earliest London-Doha departure that "
                  "day is QR104 at 08:25.")

    elif index == 4:
        b.goto("/")
        b.step("/en/flight-status.html?mode=route&from=DOH&to=SYD&date=2026-09-24",
               "goto", {})
        b.goto("/en/destinations.html")
        b.goto("/en/destinations/flights-to-sydney.html")
        answer = ("QR908 operates nonstop from Doha to Sydney on the Boeing "
                  "777-300ER, departing at 20:05. The Sydney guide lists the Sydney "
                  "Opera House first under Things to do.")

    elif index == 5:
        b.login("alice.j@test.com")
        b.goto("/en/manage-booking.html")
        b.goto("/en/manage-booking/QR92XN.html")
        stmts = [("UPDATE bookings SET status='cancelled' WHERE pnr='QR92XN'", ())]
        answer = ("Cancelled my Paris trip QR92XN (QR041 Doha to Paris on 2 "
                  "November 2026). The site confirmed the booking was cancelled and "
                  "the refund is processed to the original payment method. My other "
                  "trip QK17TP is unchanged.")

    elif index == 6:
        b.login("david.k@test.com")
        b.step("/en/baggage.html?fare=First+Elite&route=weight", "goto", {})
        b.goto("/en/manage-booking.html")
        b.goto("/en/manage-booking/QD77LW.html")
        stmts = [("UPDATE bookings SET extra_bags=2, total_paid=69731"
                  " WHERE pnr='QD77LW'", ())]
        answer = ("First Elite includes 50kg (110lb) of checked baggage on "
                  "weight-concept routes. Added 2 extra 23kg baggage pieces to "
                  "booking QD77LW at USD 140 per piece; fee charged USD 280. The "
                  "new total shown on the booking is USD 69,731.")

    elif index == 7:
        b.login("carol.d@test.com")
        b.goto("/en/check-in.html")
        b.goto("/en/check-in/QC08BV.html")
        b.goto("/en/check-in/QC08BV/boarding-pass.html")
        stmts = [
            ("UPDATE bookings SET checked_in=1, total_paid=6847 WHERE pnr='QC08BV'", ()),
            ("UPDATE passengers SET seat_out='30A' WHERE booking_id=(SELECT id FROM"
             " bookings WHERE pnr='QC08BV') AND first_name='Carol'", ()),
            ("UPDATE passengers SET seat_out='30B' WHERE booking_id=(SELECT id FROM"
             " bookings WHERE pnr='QC08BV') AND first_name='James'", ()),
            ("UPDATE booking_legs SET seat_fee=60 WHERE booking_id=(SELECT id FROM"
             " bookings WHERE pnr='QC08BV') AND flight_number=701", ()),
        ]
        answer = ("Checked in booking QC08BV: Carol Davis in seat 30A and James "
                  "Davis in seat 30B. Boarding gate F22, boarding time 07:20, seat "
                  "fees charged USD 60.")

    elif index == 8:
        b.login("bob.c@test.com")
        b.goto("/en/manage-booking/QB55MD.html")
        b.goto("/en/Privilege-Club/dashboard.html")
        stmts = [
            ("UPDATE bookings SET cabin='Business', avios_redeemed=1948"
             " WHERE pnr='QB55MD'", ()),
            ("UPDATE users SET avios=13352 WHERE email='bob.c@test.com'", ()),
            ("INSERT INTO activities (user_id, kind, avios, qpoints, description,"
             " occurred_at) VALUES (2,'redeem',-1948,0,'Upgrade to Business Class"
             " on QR826 (DOH→BKK)','2026-09-24')", ()),
        ]
        answer = ("Upgraded booking QB55MD to Business Class using 1,948 Avios; "
                  "the booking page showed my Privilege Club balance of 15,300 "
                  "Avios before the upgrade. The booking now shows Business Class. "
                  "My Avios balance on the dashboard afterwards is 13,352. Recent "
                  "activity: Upgrade to Business Class on QR826 (DOH→BKK), "
                  "-1,948 Avios.")

    elif index == 9:
        b.login("alice.j@test.com")
        b.goto("/en/Privilege-Club/avios-calculator.html")
        b.fill("/en/Privilege-Club/avios-calculator.html", "JFK")
        answer = ("A one-way Business Class flight from Doha to New York JFK earns "
                  "a Gold member 3,766 Avios and 431 Qpoints. The calculator used "
                  "flight QR701, scheduled departure 08:00.")

    elif index == 10:
        b.goto("/en/Privilege-Club/membership-tiers.html")
        b.login("bob.c@test.com")
        b.goto("/en/Privilege-Club/dashboard.html")
        b.login("alice.j@test.com")
        b.goto("/en/Privilege-Club/dashboard.html")
        answer = ("320 Qpoints within 12 months qualifies for Gold, which comes "
                  "with oneworld Sapphire status. The next tier up, Platinum, needs "
                  "600 Qpoints within 12 months, so 280 more. Gold gives a 20kg "
                  "extra baggage allowance, or one piece depending on the route. "
                  "Bob is Silver, 90 Qpoints from Gold; Alice is Gold, 185 Qpoints "
                  "from Platinum. Bob is the closest of the three of us to his "
                  "next tier.")

    elif index == 11:
        b.goto("/en/destinations.html?region=themiddleeast")
        b.goto("/en/destinations/flights-to-doha.html")
        answer = ("The Middle East city whose Things to do mentions the Museum of "
                  "Islamic Art is Doha. Its Activities section lists strolling the "
                  "Corniche (a dhow boat ride) and visiting The Pearl.")

    elif index == 12:
        b.goto("/en/destinations/flights-to-seoul.html")
        b.goto("/en/destinations/flights-to-tokyo.html")
        answer = ("Tokyo's Activities section mentions the Yayoi Kusama Museum. "
                  "The Seoul City Wall Trail (Naksan Section) stretches 18.6 "
                  "kilometres according to Seoul's Activities section, which also "
                  "suggests staying in Bukchon Hanok Village; Seoul's Things to do "
                  "highlights Changdeokgung, a Joseon dynasty palace with a Secret "
                  "Garden. Tokyo's Food section says you can sample amazing sushi "
                  "at the Tsukiji Outer Market, and its Activities section calls "
                  "Yoyogi Park perfect for jogging and picnics.")

    elif index == 13:
        pnr = "DD78IJ"
        b.goto("/en/offers.html")
        b.goto("/en/offers/motogp-adventures.html")
        b.goto("/")
        b.step("/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1"
               "&children=0&cabin=Economy&promo=MOTOGP26", "goto", {})
        b.step("/en/booking/passenger-details.html?from=DOH&to=LHR&depart=2026-10-08"
               "&adults=1&children=0&cabin=Economy&fare=ECO_CLASSIC&flight=1"
               "&promo=MOTOGP26", "goto", {})
        b.step("/en/booking/payment.html", "goto", {})
        b.step(f"/en/booking/confirmation.html?pnr={pnr}", "goto", {})
        stmts = honest_booking_statements(
            pnr, cabin="Economy", fare="ECO_CLASSIC", adults=1, total=796,
            legs=[(1, "DOH", "LHR", "2026-10-08", "08:00", "13:45", "388", 5215, 790)],
            passengers=[("Mr", "Leo", "Martin", "adult")],
            promo="MOTOGP26",
            contact_email="leo.martin@example.com", contact_last="Martin",
            card_last4="5556")
        answer = (f"The MotoGP promo code is MOTOGP26. Discount at payment USD 79. "
                  f"Total charged USD 796. Booking reference {pnr}.")

    elif index == 14:
        b.step("/en/flight-status.html?mode=route&from=DOH&to=LHR&date=2026-09-24",
               "goto", {})
        b.goto("/en/our-fleet.html")
        b.goto("/en/our-fleet/Airbus-A350-900.html")
        b.goto("/en/our-fleet/Airbus-A380-800.html")
        answer = ("QR105 from Doha to London Heathrow is operated by the Airbus "
                  "A350-900, which features Qsuite and seats 283 passengers; its "
                  "Business Class cabin occupies rows 1-8 and Economy rows 30-51. "
                  "The largest aircraft in the fleet is the Airbus A380-800 with "
                  "517 seats; its First Class cabin occupies rows 1-3.")

    elif index == 15:
        b.step("/en/baggage.html?fare=Economy+Comfort&route=americas", "goto", {})
        b.step("/en/baggage.html?fare=Business+Elite&route=weight", "goto", {})
        b.step("/en/baggage.html?fare=Economy+Lite&route=americas", "goto", {})
        b.goto("/en/help.html?q=carry-on")
        answer = ("Economy Comfort on piece-concept routes includes 2 pieces up to "
                  "23kg (50lb) each. Each extra 23kg piece on Doha-Sao Paulo (over "
                  "8,000km) costs USD 140. Business Elite on weight-concept routes "
                  "includes 40kg (88lb) of checked baggage. Economy Lite on "
                  "piece-concept routes includes 1 piece up to 23kg (50lb). "
                  "Economy carry-on is 1 piece up to 7kg.")

    elif index == 16:
        b.goto("/en/help.html?q=hard+of+hearing")
        b.goto("/en/help.html?q=medical+assistance+form")
        b.goto("/en/help.html?q=firearms+Oman")
        b.goto("/en/help.html?q=proof+of+travel+certificate")
        b.goto("/en/help.html?q=infants+baggage")
        answer = ("The dedicated 24-hour support number for hard-of-hearing "
                  "passengers is +1 833 607 2675. The medical assistance form must "
                  "be submitted between 7 days and 48 hours before departure. "
                  "Firearms for Oman must be declared more than 19 days prior to "
                  "departure. Proof-of-travel certificates can be requested for "
                  "up to 12 months from the date of travel. Infants can carry one "
                  "baby stroller or collapsible carrycot at no additional cost.")

    elif index == 17:
        b.goto("/en/Privilege-Club/join.html")
        b.fill("/en/Privilege-Club/join.html", "Fiona")
        b.fill("/en/Privilege-Club/join.html", "Gray")
        b.fill("/en/Privilege-Club/join.html", "fiona.gray@example.com")
        b.fill("/en/Privilege-Club/join.html", "Ireland")
        b.goto("/en/Privilege-Club/dashboard.html")
        b.goto("/en/Privilege-Club/membership-tiers.html")
        stmts = [("INSERT INTO users (id, email, password_hash, title, first_name,"
                  " last_name, tier, avios, qpoints, qcredits, membership_no,"
                  " country, mobile, joined) VALUES (5, 'fiona.gray@example.com',"
                  " 'pbkdf2:sha256:1000000$fixture', 'Ms', 'Fiona', 'Gray',"
                  " 'Burgundy', 0, 0, 0, 'QRPC0000005', 'Ireland',"
                  " '+353 86 123 4567', '2026-09-24')", ())]
        answer = ("Created the Privilege Club account for Fiona Gray. Membership "
                  "number QRPC0000005, starting tier Burgundy with a 10% seat "
                  "selection discount, joined 2026-09-24. 150 Qpoints within "
                  "12 months upgrade a member to Silver.")

    elif index == 18:
        b.login("carol.d@test.com")
        b.goto("/en/Privilege-Club/dashboard/my-profile.html")
        b.fill("/en/Privilege-Club/dashboard/my-profile.html", "Brazil")
        b.fill("/en/Privilege-Club/dashboard/my-profile.html", "+55 11 98765 4321")
        b.goto("/en/Privilege-Club/dashboard.html")
        stmts = [("UPDATE users SET country='Brazil', mobile='+55 11 98765 4321'"
                  " WHERE email='carol.d@test.com'", ())]
        answer = ("Profile updated to country Brazil and mobile +55 11 98765 4321. "
                  "The site confirmed: Your profile has been updated. The profile "
                  "shows Carol Davis, carol.d@test.com, tier Burgundy, Avios "
                  "balance 4,200 and Qpoints 60. The most recent entry in my "
                  "recent activity is Privilege Club partner bonus - Qatar Duty "
                  "Free, +2,500 Avios.")

    elif index == 19:
        pnr = "EE90KL"
        b.goto("/")
        b.step("/en/search-results.html?from=DOH&to=DXB&depart=2026-10-05&adults=2"
                "&children=0&cabin=Economy", "goto", {})
        b.step("/en/booking/passenger-details.html?from=DOH&to=DXB&depart=2026-10-05"
               "&adults=2&children=0&cabin=Economy&fare=ECO_LITE&flight=1002",
               "goto", {})
        b.step("/en/booking/payment.html", "goto", {})
        b.step(f"/en/booking/confirmation.html?pnr={pnr}", "goto", {})
        stmts = honest_booking_statements(
            pnr, cabin="Economy", fare="ECO_LITE", adults=2, total=314,
            legs=[(1002, "DOH", "DXB", "2026-10-05", "10:00", "12:15", "320", 379, 280)],
            passengers=[("Mr", "Ravi", "Patel", "adult"), ("Ms", "Anaya", "Patel", "adult")],
            contact_email="ravi.patel@example.com", contact_last="Patel",
            card_last4="4444")
        answer = (f"Economy Lite totals USD 280 for two passengers versus Economy "
                  f"Comfort USD 430, so Economy Lite is cheaper. Booked Economy "
                  f"Lite for Ravi Patel and his daughter Anaya Patel: total "
                  f"charged USD 314. Booking reference {pnr}.")

    b.done(answer)
    copy_db(seed, root / "initial.db")
    if stmts:
        mutate_db(seed, after, stmts)
    else:
        copy_db(seed, after)
    return root, answer


HONEST_ANSWERS = {}
