"""Deterministic verifier contract tests for the CARNIVAL CRUISE mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (counts, prices, day
    schedules, booking fixtures, excursion extremes, info-page copy),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots; stateful tasks carry the exact expected DB mutation) MUST PASS,
  - a no-op run (homepage only, empty answer) MUST FAIL for every task,
  - a homepage-only run with a fabricated correct-sounding answer MUST FAIL,
  - near-miss wrong answers MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, missing / 1x1 /
    reused screenshots, mutated after-DB on read-only tasks, missing or
    over-mutated state on stateful tasks, upstream origin, truncated run)
    MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed (DB snapshots come from the frozen seed).
"""
import json
import os
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "carnival_cruise.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from verify_lib import (  # noqa: E402
    affirm_money, affirm_time, affirm_score, contains_count, day_number,
    affirms, norm,
)

BASE = "http://localhost:46062"


# ---------------------------------------------------------------- PNG fixture
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for y in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- run fixture
def build_run(root, steps, final_answer, shots_n=None, mutate=None, terminated=True):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    for i in range(frames):
        (root / "screenshots" / f"step_{i:03d}.png").write_bytes(make_png(1000 + i))
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        traj_steps.append({
            "step": i, "url": url, "title": "fixture", "page_text": text,
            "thought": "fixture thought", "action": action, "params": params,
            "observed_text": text, "observed_text_before": text,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": "fixture", "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 30, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": "",
    }
    (root / "trajectory.json").write_text(json.dumps(traj, indent=1))
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "WH_SITE": "carnival_cruise"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-500:],
                   "stderr": proc.stderr[-500:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB helpers
def _seed_conn():
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _uid(db, email):
    con = sqlite3.connect(db)
    row = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    con.close()
    return row[0]


def _sailing_int_id(db, sailing_code):
    con = sqlite3.connect(db)
    row = con.execute("SELECT id FROM sailings WHERE sailing_id=?", (sailing_code,)).fetchone()
    con.close()
    return row[0]


def mut_t13(db):
    """The exact DB state a completed task-13 booking produces."""
    con = sqlite3.connect(db)
    uid = (con.execute("SELECT MAX(id) FROM users").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO users (id,email,password_hash,first_name,last_name,phone,address1,
        address2,city,state,zip_code,country,vifp_number,rewards_points,rewards_stars,
        rewards_tier,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, "jordan.rivera@example.com", "$2b$12$fixturehashfixturehashfixturehash",
                 "Jordan", "Rivera", "", "", "", "", "", "", "United States",
                 "VA1B2C3", 0, 0, "Blue", "2026-09-22 12:00:00"))
    bid = (con.execute("SELECT MAX(id) FROM bookings").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO bookings (id,booking_number,user_id,sailing_id,room_type,room_category,
        guests,lead_guest,cabin_number,total_price,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bid, "CCL2609AB12", uid, _sailing_int_id(db, "22233"), "interior", "",
                 2, "Jordan Rivera", "5C111", 858.0, "confirmed", "2026-09-22 12:00:00"))
    pid = (con.execute("SELECT MAX(id) FROM payment_methods").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO payment_methods (id,user_id,card_type,last4,holder_name,exp_month,
        exp_year,is_default) VALUES (?,?,?,?,?,?,?,?)""",
                (pid, uid, "Visa", "1111", "Jordan Rivera", 9, 2028, 0))
    con.commit()
    con.close()


def mut_t17(db):
    """The exact DB state a completed task-17 excursion add produces."""
    con = sqlite3.connect(db)
    bid = con.execute("SELECT id FROM bookings WHERE booking_number='9N382702'").fetchone()[0]
    eid = con.execute("SELECT id FROM excursions WHERE code='409063'").fetchone()[0]
    nid = (con.execute("SELECT MAX(id) FROM booking_excursions").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO booking_excursions (id,booking_id,excursion_id,guests,price)
        VALUES (?,?,?,?,?)""", (nid, bid, eid, 2, 251.98))
    con.execute("UPDATE bookings SET total_price=1589.98 WHERE id=?", (bid,))
    con.commit()
    con.close()


def mut_readonly(db):
    """An unrelated write that read-only tasks must reject."""
    con = sqlite3.connect(db)
    con.execute("UPDATE users SET rewards_points = rewards_points + 1 WHERE email=?",
                ("alice.j@test.com",))
    con.commit()
    con.close()


# ---------------------------------------------------------------- honest steps
def S(url, action="navigate", params=None, text=""):
    return (url, action, params or {}, text)


SEARCH = BASE + "/cruise-search"
BAW_URL = BASE + "/itinerary/3-day-the-bahamas-cruise/miami/conquest/3-days/baw"
BERMUDA_URL = BASE + "/itinerary/5-day-bermuda-cruise/manhattan-new-york-city/firenze/5-days/br6"
BAJA_URL = BASE + "/itinerary/4-day-baja-mexico-cruise/long-beach-los-angeles/firenze/4-days/lxq"

HONEST = {
    0: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=MIA&dur=D1&sort=fromprice",
              text="3-Day The Bahamas from Miami, FL Carnival Conquest From $183"),
        ], answer="The cheapest 3-day cruise departing from Miami, FL is "
                  "\"3-Day The Bahamas from Miami, FL\" aboard Carnival Conquest, "
                  "with a starting price of $183 per person."),
    1: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=GAL", text="56 Cruise Results"),
        ], answer="Filtering the cruise search to Galveston, TX shows 56 cruise itineraries."),
    2: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?dest=A", text="8 Cruise Results 7 Days"),
        ], answer="There are 8 cruise results for Alaska. The shortest Alaska cruise "
                  "is 7 days long."),
    3: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=MIA&dur=D1&sort=fromprice",
              text="5-Day The Bahamas from Miami, FL Carnival Sunrise $215 Celebration Key "
                   "RelaxAway, Half Moon Cay"),
        ], answer="The cheapest 5-day cruise from Miami visiting both Celebration Key and "
                  "RelaxAway, Half Moon Cay is \"5-Day The Bahamas from Miami, FL\" aboard "
                  "Carnival Sunrise, starting at $215 per person."),
    4: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=MSY&sort=-duration",
              text="14-Day Caribbean & Panama from New Orleans, LA 14 Days $1299"),
        ], answer="The longest cruise departing from New Orleans, LA is \"14-Day Caribbean & "
                  "Panama from New Orleans, LA\". It lasts 14 days and its starting price per "
                  "person is $1299."),
    5: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=MIA&sort=-fromprice",
              text="7-Day Eastern Caribbean from Miami, FL $1154"),
        ], answer="The cruise with the highest starting price among Miami departures is "
                  "\"7-Day Eastern Caribbean from Miami, FL\" at $1154 per person."),
    6: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/search?q=BOLT",
              text="BOLT: ULTIMATE SEA COASTER On Carnival Celebration On Carnival Jubilee On Mardi Gras"),
        ], answer="The Carnival ships that offer BOLT: The Ultimate Sea Coaster are: "
                  "Carnival Celebration, Carnival Jubilee, Mardi Gras."),
    7: dict(steps=[
            S(BASE + "/"),
            S(BAW_URL, text="Day 3: Celebration Key™ Arrive 8:00 AM - Departs 4:00 PM"),
        ], answer="The ship calls at Celebration Key on day 3 of the cruise and departs "
                  "that day at 4:00 PM."),
    8: dict(steps=[
            S(BASE + "/"),
            S(BERMUDA_URL, text="Day 3: Bermuda Arrive 4:00 PM Day 4: Bermuda Departs 4:00 PM"),
        ], answer="The ship stays in Bermuda on days 3 and 4 of the cruise (arriving day 3 "
                  "at 4:00 PM, departing day 4 at 4:00 PM) — 2 days in Bermuda before "
                  "sailing back, with day 4 the only full day in port."),
    9: dict(steps=[
            S(BASE + "/"),
            S(BAJA_URL, text="Day 2: Catalina Island Arrive 8:00 AM - Departs 5:00 PM Day 3: Ensenada"),
        ], answer="Besides Ensenada, the ship visits Catalina Island, on day 2 of the cruise."),
    10: dict(steps=[
            S(BASE + "/"),
            S(BAW_URL, text="Get to Know Carnival Conquest Guy's Burger Joint RedFrog Rum Bar"),
        ], answer="The burger restaurant included in the cruise fare is Guy's Burger Joint."),
    11: dict(steps=[
            S(BASE + "/"),
            S(SEARCH + "?port=GAL&dur=D2&sort=fromprice",
              text="7-Day Western Caribbean from Galveston, TX Carnival Breeze $632 Grand Cayman Cozumel"),
        ], answer="The cheapest 7-day Galveston cruise visiting both Grand Cayman and Cozumel "
                  "is \"7-Day Western Caribbean from Galveston, TX\" aboard Carnival Breeze, "
                  "starting at $632 per person."),
    12: dict(steps=[
            S(BASE + "/"),
            S(BAJA_URL, text="Day 5: Long Beach (Los Angeles) Arrive 8:00 AM"),
        ], answer="The ship arrives back at Long Beach on the final day at 8:00 AM."),
    13: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/register", "input",
              {"first_name": "Jordan", "last_name": "Rivera",
               "email": "jordan.rivera@example.com"}, "Create Your Account"),
            S(BASE + "/booking?embkCode=MIA&itinCode=BAW&durDays=3&shipCode=CQ&sailingID=22233&numGuests=2",
              text="3-Day The Bahamas from Miami Interior $429"),
            S(BASE + "/booking?embkCode=MIA&itinCode=BAW&durDays=3&shipCode=CQ&sailingID=22233&numGuests=2&roomType=interior&step=guests",
              "click", {"selector": "Interior SELECT"}, "Guest Details"),
            S(BASE + "/booking?embkCode=MIA&itinCode=BAW&durDays=3&shipCode=CQ&sailingID=22233&numGuests=2&roomType=interior&step=payment",
              "input", {"lead_guest": "Jordan Rivera", "guests": 2}, "Total Due $858.00"),
            S(BASE + "/booking?embkCode=MIA&itinCode=BAW&durDays=3&shipCode=CQ&sailingID=22233&numGuests=2&roomType=interior&step=confirmation&bookingNumber=CCL2609AB12",
              "input", {"card_number": "4111111111111111", "exp_month": "09", "exp_year": "2028"},
              "You're Booked! Booking Number CCL2609AB12 Total Paid $858.00"),
        ], answer="The booking is confirmed. Booking number: CCL2609AB12. Total price: "
                  "$858.00 ($429 per person x 2 adults, Interior stateroom).",
              mutate=mut_t13),
    14: dict(steps=[
            S(BASE + "/login", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/booked/manage/9N382701",
              text="Booking 9N382701 Premium Balcony Cabin 5C102"),
        ], answer="Booking 9N382701: cabin number 5C102, stateroom category Premium Balcony."),
    15: dict(steps=[
            S(BASE + "/login", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/booked/manage", text="9N382701 3-Day The Bahamas Sep 25 - 28"),
        ], answer="My upcoming cruise departing in September 2026 is booking 9N382701, "
                  "\"3-Day The Bahamas from Miami, FL\". I did not confirm any cancellation."),
    16: dict(steps=[
            S(BASE + "/login", "input", {"email": "bob.c@test.com", "password": "TestPass123!"}),
            S(BASE + "/booked/manage/9N510304",
              text="Beach Escape: Island's Beach Club, Pool & Snorkel Cozumel 2 $95.98"),
        ], answer="Booking 9N510304 already has the shore excursion \"Beach Escape: Island's "
                  "Beach Club, Pool & Snorkel\" added, for 2 guests, at $95.98."),
    17: dict(steps=[
            S(BASE + "/login", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(BASE + "/booked/manage/9N382702",
              text="Pearl Cove Beach Club: All Inclusive $125.99 ADD TO BOOKING"),
            S(BASE + "/booked/manage/9N382702", "click",
              {"selector": "ADD TO BOOKING"}, "Total $1589.98"),
        ], answer="The Pearl Cove Beach Club: All Inclusive excursion was added for 2 guests "
                  "to booking 9N382702. The new total price of the booking is $1589.98.",
              mutate=mut_t17),
    18: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/shore-excursions/cozumel?sort=price",
              text="The Cruiser's Choice: Downtown Vibes & Beach Club $44.99"),
        ], answer="The cheapest Cozumel excursion is \"The Cruiser's Choice: Downtown Vibes "
                  "& Beach Club\" at $44.99 per person."),
    19: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/shore-excursions/cozumel",
              text="Fully Accessible Private Van & Expert Host $629.99"),
        ], answer="The most expensive Cozumel excursion is \"Fully Accessible Private Van & "
                  "Expert Host\" at $629.99."),
    20: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/shore-excursions/celebration-key/pearl-cove-beach-club-all-inclusive-409063",
              text="Pearl Cove Beach Club: All Inclusive $125.99 6.0 Hours"),
        ], answer="The Pearl Cove Beach Club: All Inclusive excursion at Celebration Key "
                  "costs $125.99 per person and lasts 6.0 hours."),
    21: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/shore-excursions/juneau",
              text="Evening Whale Quest With Dinner 5.0 (6 reviews)"),
        ], answer="The Juneau excursion with the highest rating and most reviews is "
                  "\"Evening Whale Quest With Dinner\" — 5.0 stars, 6 reviews."),
    22: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/shore-excursions/amber-cove",
              text="Dolphin Swim & Ocean World Day Pass Minimum Age: 6"),
        ], answer="The minimum age for the Dolphin Swim & Ocean World Day Pass excursion "
                  "at Amber Cove is 6 years old."),
    23: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/cruise-ships/carnival-celebration",
              text="Zones & Features Celebration Central The Gateway Summer Landing 820 "
                   "Biscayne Lido THE ULTIMATE PLAYGROUND"),
        ], answer="Carnival Celebration lists 6 Zones: Celebration Central, The Gateway, "
                  "Summer Landing, 820 Biscayne, Lido, and The Ultimate Playground."),
    24: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/cruise-ships/mardi-gras",
              text="Onboard Dining Chibang! included Street Eats included Big Chicken "
                   "included Cucina del Capitano included"),
        ], answer="The Mardi Gras dining venues included in the cruise fare are: Chibang!, "
                  "Street Eats, Big Chicken, and Cucina del Capitano."),
    25: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/cruise-ships/carnival-jubilee", text="Sails from Galveston, TX"),
        ], answer="Carnival Jubilee sails from the home port of Galveston, TX."),
    26: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/cruise-ships/carnival-celebration",
              text="BOLT: ULTIMATE SEA COASTER additional Latitudes additional The Golden "
                   "Jubilee additional CLOUD 9 SPA additional"),
        ], answer="Besides BOLT: The Ultimate Sea Coaster, two other Carnival Celebration "
                   "experiences marked Additional are Latitudes and The Golden Jubilee."),
    27: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/drink-packages", text="CHEERS! $69.95 / Person per Day"),
        ], answer="The CHEERS! beverage package costs $69.95 per person per day."),
    28: dict(steps=[
            S(BASE + "/"),
            S(BASE + "/about-carnival/contact-us",
              text="Saturday – Sunday 9:00 a.m. to 6:00 p.m. ET"),
        ], answer="On weekends (Saturday and Sunday), Customer Service is available by "
                  "phone from 9:00 a.m. to 6:00 p.m. ET."),
    29: dict(steps=[
            S(BASE + "/login", "input", {"email": "carol.d@test.com", "password": "TestPass123!"}),
            S(BASE + "/favorites",
              text="3-Day The Bahamas from Miami, FL 5-Day The Bahamas 7-Day 9-Day"),
        ], answer="I have 5 cruises saved. The shortest saved cruise is \"3-Day The Bahamas "
                  "from Miami, FL\" (3 days)."),
}

# near-miss wrong answers (plausible agent mistakes; each MUST fail its task)
WRONG = {
    0: "The cheapest 3-day cruise from Miami is \"3-Day The Bahamas from Miami, FL\" "
       "starting at $272 per person.",
    1: "Filtering to Galveston shows 55 cruise itineraries.",
    2: "There are 8 Alaska cruise results; the shortest is 5 days.",
    3: "The cheapest matching cruise is \"5-Day The Bahamas from Miami, FL\" aboard "
       "Carnival Conquest at $246 per person.",
    4: "The longest New Orleans cruise is the 8-Day The Bahamas at $870.",
    5: "The highest-priced Miami cruise is the 8-Day Southern Caribbean at $1039.",
    6: "BOLT is offered on Carnival Celebration and Mardi Gras.",
    7: "The ship calls at Celebration Key on day 2 and departs at 5:00 PM.",
    8: "The ship stays in Bermuda on days 4 and 5 — 2 days.",
    9: "Besides Ensenada the ship visits Nassau on day 2.",
    10: "The burger restaurant is RedFrog Rum Bar.",
    11: "The cheapest is \"7-Day Western Caribbean from Galveston, TX\" aboard Carnival "
       "Dream at $806.",
    12: "The ship arrives back at Long Beach at 10:00 AM.",
    13: "Booking number: CCL2609AB12. Total price: $429.00.",
    14: "Booking 9N382701: cabin number 6D103, stateroom category Interior.",
    15: "My September 2026 cruise is booking 9N382702, the 7-Day Eastern Caribbean.",
    16: "The added excursion is \"Top 10 Best of Miami: MIA Airport Transfer\" for 2 "
       "guests at $119.98.",
    17: "The excursion was added to booking 9N382702; the new total is $1463.98.",
    18: "The cheapest Cozumel excursion is \"Beach Escape: Island's Beach Club, Pool & "
       "Snorkel\" at $47.99.",
    19: "The most expensive Cozumel excursion is \"Xplor Park - All Inclusive Adventure\" "
       "at $186.99.",
    20: "Pearl Cove Beach Club costs $223.99 per person and lasts 4 hours.",
    21: "The top Juneau excursion is \"Taku Glacier Helicopter Landing & Airboat Ride\" — "
       "5.0 stars, 4 reviews.",
    22: "The minimum age for the Dolphin Swim & Ocean World Day Pass is 10.",
    23: "Carnival Celebration lists 7 Zones: Celebration Central, The Gateway, Summer "
       "Landing, 820 Biscayne, Lido, The Ultimate Playground and Loft 19.",
    24: "The included Mardi Gras dining venues are Chibang! and Big Chicken.",
    25: "Carnival Jubilee sails from Miami, FL.",
    26: "Besides BOLT, the Celebration page shows Waterworks and Family Feud Live marked "
       "Additional.",
    27: "The CHEERS! package costs $64.95 per person per day.",
    28: "Customer Service is available on weekends from 9:00 a.m. to 10:00 p.m. ET.",
    29: "I have 4 cruises saved; the shortest is the 5-Day The Bahamas from Miami.",
}


class ContractBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wh-ccl-tests-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def honest_dir(self, n, **kw):
        spec = HONEST[n]
        d = self.tmp / f"honest_{n}"
        shutil.rmtree(d, ignore_errors=True)
        return build_run(d, spec["steps"], spec["answer"], mutate=spec.get("mutate"), **kw)

    def run_verdict(self, n, d):
        rc, verdict = run_verifier(n, d)
        return verdict.get("pass") is True and rc == 0, verdict


class TestHonestPass(ContractBase):
    def test_honest_fixtures_all_pass(self):
        bad = []
        for n in range(30):
            ok, verdict = self.run_verdict(n, self.honest_dir(n))
            if not ok:
                bad.append((n, verdict.get("reason")))
        self.assertEqual(bad, [], f"honest fixtures must pass: {bad}")


class TestNoopFails(ContractBase):
    def _noop(self, answer=""):
        d = self.tmp / "noop"
        shutil.rmtree(d, ignore_errors=True)
        return build_run(d, [S(BASE + "/")], answer)

    def test_noop_empty_answer_fails_all(self):
        d = self._noop("")
        bad = [n for n in range(30)
               if self.run_verdict(n, d)[0]]
        self.assertEqual(bad, [], f"no-op runs must fail every verifier, passed: {bad}")

    def test_homepage_only_with_fabricated_answer_fails_all(self):
        # correct-sounding answers without any on-site navigation = shortcut
        bad = []
        for n in range(30):
            d = self.tmp / f"fab_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, [S(BASE + "/")], HONEST[n]["answer"],
                      mutate=HONEST[n].get("mutate"))
            if self.run_verdict(n, d)[0]:
                bad.append(n)
        self.assertEqual(bad, [], f"homepage-only runs must fail, passed: {bad}")


class TestWrongAnswersFail(ContractBase):
    def test_wrong_answers_fail(self):
        bad = []
        for n, wrong in WRONG.items():
            spec = HONEST[n]
            d = self.tmp / f"wrong_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, spec["steps"], wrong, mutate=spec.get("mutate"))
            ok, verdict = self.run_verdict(n, d)
            if ok:
                bad.append(n)
        self.assertEqual(bad, [], f"wrong answers must fail, passed: {bad}")


class TestShortcutFails(ContractBase):
    def test_correct_answer_wrong_pages_fail(self):
        # the agent never opens the anchor page (only the homepage + an
        # unrelated page) but recites the right answer from memory
        bad = []
        for n in range(30):
            spec = HONEST[n]
            steps = [S(BASE + "/"), S(BASE + "/cruise-deals", text="deals")]
            d = self.tmp / f"shortcut_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, steps, spec["answer"], mutate=spec.get("mutate"))
            if self.run_verdict(n, d)[0]:
                bad.append(n)
        self.assertEqual(bad, [], f"shortcut runs must fail, passed: {bad}")


class TestTamperedPackages(ContractBase):
    def test_missing_trajectory_fails(self):
        d = self.honest_dir(7)
        (d / "trajectory.json").unlink()
        ok, verdict = run_verifier(7, d)
        self.assertFalse(ok and verdict.get("pass"))
        self.assertNotEqual(verdict.get("reason"), None)

    def test_corrupt_trajectory_fails(self):
        d = self.honest_dir(7)
        (d / "trajectory.json").write_text("{not json")
        ok, verdict = run_verifier(7, d)
        self.assertFalse(verdict.get("pass") is True)

    def test_missing_screenshots_fail(self):
        for n in (0, 13):
            d = self.honest_dir(n)
            for p in (d / "screenshots").glob("*.png"):
                p.unlink()
            ok, verdict = run_verifier(n, d)
            self.assertFalse(verdict.get("pass") is True, f"task {n} missing shots")

    def test_tiny_screenshots_fail(self):
        d = self.honest_dir(0)
        tiny = make_png(7, width=8, height=8)[:33] + b"IDAT" + b"\x00\x00\x00\x00"
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(tiny)
        ok, verdict = run_verifier(0, d)
        self.assertFalse(verdict.get("pass") is True)

    def test_identical_frames_fail(self):
        d = self.honest_dir(3)
        one = make_png(42)
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(one)
        ok, verdict = run_verifier(3, d)
        self.assertFalse(verdict.get("pass") is True)

    def test_readonly_db_tamper_fails(self):
        for n in (0, 7, 14, 29):
            spec = HONEST[n]
            d = self.tmp / f"rotamper_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, spec["steps"], spec["answer"], mutate=mut_readonly)
            ok, verdict = run_verifier(n, d)
            self.assertFalse(verdict.get("pass") is True, f"task {n} read-only tamper")

    def test_stateful_missing_mutation_fails(self):
        # the agent claims success but the DB is unchanged (state mismatch)
        for n in (13, 17):
            spec = HONEST[n]
            d = self.tmp / f"nomut_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, spec["steps"], spec["answer"])  # no mutate
            ok, verdict = run_verifier(n, d)
            self.assertFalse(verdict.get("pass") is True, f"task {n} state mismatch")

    def test_stateful_extra_mutation_fails(self):
        for n, base_mut in ((13, mut_t13), (17, mut_t17)):
            def both(db, base_mut=base_mut):
                base_mut(db)
                mut_readonly(db)  # an unrelated change must fail the preserve check
            spec = HONEST[n]
            d = self.tmp / f"extramut_{n}"
            shutil.rmtree(d, ignore_errors=True)
            build_run(d, spec["steps"], spec["answer"], mutate=both)
            ok, verdict = run_verifier(n, d)
            self.assertFalse(verdict.get("pass") is True, f"task {n} extra mutation")

    def test_upstream_origin_fails(self):
        spec = HONEST[7]
        steps = [S("https://www.carnival.com/itinerary/3-day-the-bahamas-cruise/miami/conquest/3-days/baw",
                   text="Day 3: Celebration Key")]
        d = self.tmp / "upstream"
        shutil.rmtree(d, ignore_errors=True)
        build_run(d, steps, spec["answer"])
        ok, verdict = run_verifier(7, d)
        self.assertFalse(verdict.get("pass") is True)

    def test_truncated_run_fails(self):
        d = self.honest_dir(0)
        traj = json.loads((d / "trajectory.json").read_text())
        traj["steps"] = traj["steps"][:-1]   # drop the done step
        traj["terminated"] = False
        (d / "trajectory.json").write_text(json.dumps(traj))
        ok, verdict = run_verifier(0, d)
        self.assertFalse(verdict.get("pass") is True)

    def test_wrong_sailing_booking_fails(self):
        """T13 with a booking on the wrong sailing (a different BAW date)."""
        def mut_wrong_sailing(db):
            mut_t13(db)
            con = sqlite3.connect(db)
            other = con.execute(
                "SELECT id FROM sailings WHERE sailing_id='22867'").fetchone()[0]
            con.execute("UPDATE bookings SET sailing_id=? WHERE booking_number='CCL2609AB12'",
                        (other,))
            con.commit()
            con.close()
        spec = HONEST[13]
        d = self.tmp / "wrongsailing"
        shutil.rmtree(d, ignore_errors=True)
        build_run(d, spec["steps"], spec["answer"], mutate=mut_wrong_sailing)
        ok, verdict = run_verifier(13, d)
        self.assertFalse(verdict.get("pass") is True)


class TestGroundTruth(ContractBase):
    def test_seed_counts(self):
        con = _seed_conn()
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("users", "ships", "ports", "itineraries", "itinerary_days",
                            "sailings", "excursions", "bookings", "booking_excursions",
                            "saved_cruises", "payment_methods", "destinations")}
        con.close()
        self.assertEqual(counts, {"users": 4, "ships": 31, "ports": 174,
                                  "itineraries": 482, "itinerary_days": 4062,
                                  "sailings": 2568, "excursions": 1761,
                                  "bookings": 9, "booking_excursions": 3,
                                  "saved_cruises": 18, "payment_methods": 6,
                                  "destinations": 16})

    def test_t0_cheapest_3day_mia(self):
        con = _seed_conn()
        rows = con.execute("""SELECT i.code, i.from_price FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id
            WHERE i.dur=3 AND p.code='MIA' ORDER BY i.from_price""").fetchall()
        con.close()
        self.assertEqual([dict(r) for r in rows[:2]],
                         [{"code": "BAW", "from_price": 183}, {"code": "BAV", "from_price": 272}])
        self.assertEqual(rows[0]["from_price"], answers.T0_PRICE)
        self.assertTrue(rows[0]["from_price"] < rows[1]["from_price"], "cheapest must be unique")

    def test_t1_galveston_count(self):
        con = _seed_conn()
        n = con.execute("""SELECT COUNT(*) FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id WHERE p.code='GAL'""").fetchone()[0]
        con.close()
        self.assertEqual(n, answers.T1_COUNT)

    def test_t2_alaska(self):
        con = _seed_conn()
        n, mn = con.execute("""SELECT COUNT(*), MIN(dur) FROM itineraries
            WHERE region_code IN ('AJ','GL')""").fetchone()
        con.close()
        self.assertEqual((n, mn), (answers.T2_COUNT, answers.T2_MIN_DAYS))

    def test_t3_cheapest_5day_mia_both_ports(self):
        con = _seed_conn()
        row = con.execute("""SELECT i.title, s.name ship, i.from_price FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id JOIN ships s ON s.id=i.ship_id
            WHERE i.dur=5 AND p.code='MIA' AND i.ports_csv LIKE '%Celebration Key%'
              AND i.ports_csv LIKE '%RelaxAway, Half Moon Cay%'
            ORDER BY i.from_price LIMIT 2""").fetchall()
        con.close()
        self.assertEqual((row[0]["title"], row[0]["ship"], row[0]["from_price"]),
                         (answers.T3_TITLE, answers.T3_SHIP, answers.T3_PRICE))
        self.assertLess(row[0]["from_price"], row[1]["from_price"])

    def test_t4_new_orleans_longest(self):
        con = _seed_conn()
        rows = con.execute("""SELECT i.title, i.dur, i.from_price FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id WHERE p.code='MSY'
            ORDER BY i.dur DESC LIMIT 2""").fetchall()
        con.close()
        self.assertEqual((rows[0]["title"], rows[0]["dur"], rows[0]["from_price"]),
                         (answers.T4_TITLE, answers.T4_DAYS, answers.T4_PRICE))

    def test_t5_mia_highest_price(self):
        con = _seed_conn()
        rows = con.execute("""SELECT i.title, i.from_price FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id WHERE p.code='MIA'
            ORDER BY i.from_price DESC LIMIT 2""").fetchall()
        con.close()
        self.assertEqual((rows[0]["title"], rows[0]["from_price"]),
                         (answers.T5_TITLE, answers.T5_PRICE))

    def test_t6_bolt_ships(self):
        con = _seed_conn()
        rows = [r["name"] for r in con.execute("""SELECT DISTINCT s.name FROM ship_features f
            JOIN ships s ON s.id=f.ship_id WHERE f.title LIKE '%BOLT%' ORDER BY s.name""")]
        con.close()
        self.assertEqual(sorted(rows), sorted(answers.T6_SHIPS))

    def test_t7_baw_day_schedule(self):
        con = _seed_conn()
        rows = con.execute("""SELECT d.day, d.port_name, d.arrive, d.depart FROM itinerary_days d
            WHERE d.itinerary_id=(SELECT i.id FROM itineraries i JOIN ports p ON p.id=i.departure_port_id
              JOIN ships s ON s.id=i.ship_id WHERE i.code='BAW' AND p.code='MIA'
              AND s.code='CQ' AND i.dur=3) ORDER BY d.day""").fetchall()
        con.close()
        days = [dict(r) for r in rows]
        self.assertEqual(len(days), 4)
        self.assertEqual(days[2], {"day": 3, "port_name": "Celebration Key™",
                                   "arrive": "8:00\u202fAM", "depart": "4:00\u202fPM"})

    def test_t8_bermuda_port_call(self):
        con = _seed_conn()
        for code in ("BR6", "BR1", "BR5"):
            ids = [r[0] for r in con.execute(
                "SELECT id FROM itineraries WHERE code=? AND title LIKE '%Bermuda%' AND dur=5",
                (code,))]
            self.assertTrue(ids, code)
            for iid in ids:
                rows = con.execute("""SELECT d.day, d.port_name FROM itinerary_days d
                    WHERE d.itinerary_id=? ORDER BY d.day""", (iid,)).fetchall()
                bermuda_days = [r["day"] for r in rows if r["port_name"] == "Bermuda"]
                self.assertEqual(bermuda_days, list(answers.T8_DAYS), f"{code}/{iid}")
        con.close()

    def test_t9_baja_catalina(self):
        con = _seed_conn()
        rows = con.execute("""SELECT d.day, d.port_name FROM itinerary_days d
            WHERE d.itinerary_id=(SELECT id FROM itineraries WHERE url_path LIKE
            '/itinerary/4-day-baja-mexico-cruise/long-beach-los-angeles/firenze/4-days/lxq')
            ORDER BY d.day""").fetchall()
        con.close()
        catalina = [dict(r) for r in rows if r["port_name"] == "Catalina Island"]
        self.assertEqual(catalina, [{"day": 2, "port_name": "Catalina Island"}])

    def test_t10_conquest_burger(self):
        con = _seed_conn()
        html = con.execute("SELECT long_desc_html FROM ships WHERE code='CQ'").fetchone()[0]
        con.close()
        self.assertIn(answers.T10_VENUE, html)

    def test_t11_cheapest_7day_gal(self):
        con = _seed_conn()
        rows = con.execute("""SELECT i.title, s.name ship, i.from_price FROM itineraries i
            JOIN ports p ON p.id=i.departure_port_id JOIN ships s ON s.id=i.ship_id
            WHERE i.dur=7 AND p.code='GAL' AND i.ports_csv LIKE '%Grand Cayman%'
              AND i.ports_csv LIKE '%Cozumel%' ORDER BY i.from_price LIMIT 2""").fetchall()
        con.close()
        self.assertEqual((rows[0]["title"], rows[0]["ship"], rows[0]["from_price"]),
                         (answers.T11_TITLE, answers.T11_SHIP, answers.T11_PRICE))

    def test_t12_firenze_final_day(self):
        con = _seed_conn()
        rows = con.execute("""SELECT d.day, d.port_name, d.arrive FROM itinerary_days d
            JOIN itineraries i ON i.id=d.itinerary_id WHERE i.url_path LIKE
            '/itinerary/4-day-baja-mexico-cruise/long-beach-los-angeles/firenze/%'
            ORDER BY d.day""").fetchall()
        con.close()
        last = [dict(r) for r in rows if "Long Beach" in r["port_name"]][-1]
        self.assertEqual(last["arrive"], "8:00\u202fAM")

    def test_t13_sailing_and_math(self):
        con = _seed_conn()
        s = con.execute("""SELECT s.interior, s.lowest FROM sailings s
            WHERE s.sailing_id='22233'""").fetchone()
        con.close()
        self.assertEqual((s["interior"], s["lowest"]), (429.0, 429.0))
        self.assertEqual(round(s["interior"] * 2, 2), answers.T13_TOTAL)

    def test_t14_booking_fixture(self):
        con = _seed_conn()
        b = con.execute("""SELECT b.cabin_number, b.room_category, b.total_price FROM bookings b
            WHERE b.booking_number='9N382701'""").fetchone()
        con.close()
        self.assertEqual((b["cabin_number"], b["room_category"]),
                         (answers.T14_CABIN, answers.T14_CATEGORY))

    def test_t15_alice_september_2026(self):
        con = _seed_conn()
        rows = con.execute("""SELECT b.booking_number, sl.departure_date FROM bookings b
            JOIN users u ON u.id=b.user_id JOIN sailings sl ON sl.id=b.sailing_id
            WHERE u.email='alice.j@test.com' AND b.status='confirmed'""").fetchall()
        con.close()
        sept = [r for r in rows if r["departure_date"].startswith("2026-09")]
        self.assertEqual([r["booking_number"] for r in sept], [answers.T15_BOOKING])

    def test_t16_bob_excursion(self):
        con = _seed_conn()
        row = con.execute("""SELECT e.title, be.guests, be.price FROM booking_excursions be
            JOIN bookings b ON b.id=be.booking_id JOIN excursions e ON e.id=be.excursion_id
            WHERE b.booking_number='9N510304'""").fetchone()
        con.close()
        self.assertEqual((row["title"], row["guests"], row["price"]),
                         (answers.T16_EXCURSION, answers.T16_GUESTS, answers.T16_PRICE))

    def test_t17_march_2027_booking_math(self):
        con = _seed_conn()
        row = con.execute("""SELECT b.booking_number, b.total_price FROM bookings b
            JOIN users u ON u.id=b.user_id JOIN sailings sl ON sl.id=b.sailing_id
            JOIN itineraries i ON i.id=sl.itinerary_id
            WHERE u.email='alice.j@test.com' AND b.status='confirmed'
              AND sl.departure_date LIKE '2027-03%'""").fetchone()
        exc = con.execute("SELECT price FROM excursions WHERE code='409063'").fetchone()
        con.close()
        self.assertEqual(row["booking_number"], answers.T17_BOOKING)
        self.assertEqual(row["total_price"], answers.T17_BASE_TOTAL)
        self.assertEqual(round(row["total_price"] + exc["price"] * 2, 2), answers.T17_NEW_TOTAL)

    def test_t18_t19_cozumel_extremes(self):
        con = _seed_conn()
        lo = con.execute("""SELECT title, price FROM excursions WHERE port_slug='cozumel'
            ORDER BY price LIMIT 2""").fetchall()
        hi = con.execute("""SELECT title, price FROM excursions WHERE port_slug='cozumel'
            ORDER BY price DESC LIMIT 2""").fetchall()
        con.close()
        self.assertEqual((norm(lo[0]["title"]), lo[0]["price"]),
                         (norm(answers.T18_TITLE), answers.T18_PRICE))
        self.assertLess(lo[0]["price"], lo[1]["price"])
        self.assertEqual((norm(hi[0]["title"]), hi[0]["price"]),
                         (norm(answers.T19_TITLE), answers.T19_PRICE))

    def test_t20_pearl_cove(self):
        con = _seed_conn()
        row = con.execute("""SELECT price, duration FROM excursions
            WHERE code='409063'""").fetchone()
        con.close()
        self.assertEqual((row["price"], row["duration"]), (answers.T20_PRICE, "6.0 Hours"))

    def test_t21_juneau_top(self):
        con = _seed_conn()
        rows = con.execute("""SELECT title, rating, review_count FROM excursions
            WHERE port_slug='juneau' ORDER BY rating DESC, review_count DESC""").fetchall()
        con.close()
        top = rows[0]
        self.assertEqual((top["title"], top["rating"], top["review_count"]),
                         (answers.T21_TITLE, answers.T21_RATING, answers.T21_REVIEWS))
        # unique: no other 5.0-rated excursion with 6 reviews
        self.assertEqual([r for r in rows
                         if r["rating"] == 5.0 and r["review_count"] == 6], [top])

    def test_t22_dolphin_min_age(self):
        con = _seed_conn()
        row = con.execute("""SELECT min_age FROM excursions WHERE port_slug='amber-cove'
            AND title LIKE 'Dolphin Swim & Ocean World Day Pass%'""").fetchone()
        con.close()
        self.assertEqual(int(row["min_age"]), answers.T22_MIN_AGE)

    def test_t23_celebration_zones(self):
        con = _seed_conn()
        rows = [r["title"] for r in con.execute("""SELECT f.title FROM ship_features f
            JOIN ships s ON s.id=f.ship_id WHERE s.slug='carnival-celebration'
            AND f.kind='zone' ORDER BY f.sort""")]
        con.close()
        self.assertEqual(len(rows), answers.T23_COUNT)
        folded = {norm(r) for r in rows}
        for z in answers.T23_ZONES:
            self.assertIn(norm(z), folded, z)

    def test_t24_mardi_gras_included(self):
        con = _seed_conn()
        rows = [r["title"] for r in con.execute("""SELECT f.title FROM ship_features f
            JOIN ships s ON s.id=f.ship_id WHERE s.slug='mardi-gras'
            AND f.kind='dining' AND f.cost='included'""")]
        con.close()
        self.assertEqual(sorted(rows), sorted(answers.T24_VENUES))

    def test_t25_jubilee_homeport(self):
        con = _seed_conn()
        row = con.execute("SELECT sail_from FROM ships WHERE slug='carnival-jubilee'").fetchone()
        con.close()
        self.assertIn(answers.T25_PORT, row["sail_from"])

    def test_t26_additional_set(self):
        con = _seed_conn()
        rows = [r["title"] for r in con.execute("""SELECT f.title FROM ship_features f
            JOIN ships s ON s.id=f.ship_id WHERE s.slug='carnival-celebration'
            AND f.cost='additional'""")]
        con.close()
        folded = {norm(r) for r in rows}
        for x in answers.T26_ADDITIONAL:
            self.assertIn(norm(x), folded, x)
        self.assertGreaterEqual(len(answers.T26_ADDITIONAL), answers.T26_REQUIRED)

    def test_t27_t28_info_pages(self):
        sys.path.insert(0, str(SITE))
        import _seed_info
        dp = _seed_info.INFO_PAGES["drink-packages"]["text"]
        cu = _seed_info.INFO_PAGES["contact-us"]["text"]
        self.assertIn("$69.95 / Person per Day", dp)
        self.assertIn("Saturday – Sunday 9:00 a.m. to 6:00 p.m. ET", cu)

    def test_t29_carol_favorites(self):
        con = _seed_conn()
        rows = con.execute("""SELECT i.title, i.dur FROM saved_cruises sc
            JOIN users u ON u.id=sc.user_id JOIN itineraries i ON i.id=sc.itinerary_id
            WHERE u.email='carol.d@test.com' ORDER BY i.dur""").fetchall()
        con.close()
        self.assertEqual(len(rows), answers.T29_COUNT)
        self.assertEqual(rows[0]["title"], answers.T29_SHORTEST)

    def test_answer_predicates(self):
        # integer money forms
        self.assertTrue(affirm_money("starting at $183 per person", 183))
        self.assertTrue(affirm_money("total $858.00 paid", 858))
        self.assertFalse(affirm_money("the price was $1834", 183))
        self.assertTrue(affirm_money("new total is $1,589.98", 1589.98))
        # times
        self.assertTrue(affirm_time("departs at 4:00 PM", 4, 0, "PM"))
        self.assertTrue(affirm_time("departs at 4 pm", 4, 0, "PM"))
        self.assertTrue(affirm_time("arrives 8:00 AM", 8, 0, "AM"))
        self.assertFalse(affirm_time("arrives 10:00 AM", 8, 0, "AM"))
        self.assertTrue(affirm_time("from 9:00 a.m. to 6:00 p.m. ET", 9, 0, "AM"))
        self.assertTrue(affirm_time("from 9:00 a.m. to 6:00 p.m. ET", 6, 0, "PM"))
        # day numbers
        self.assertTrue(day_number("on day 3 of the cruise", 3))
        self.assertTrue(day_number("the 2nd day", 2))
        self.assertFalse(day_number("on day 3", 4))
        # apostrophe folding
        self.assertTrue(affirms("The Cruiser’s Choice", "The Cruiser's Choice"))
        self.assertTrue(affirms("Island's Beach Club", "Island’s Beach Club"))
        # scores
        self.assertTrue(affirm_score("5.0 stars with 6 reviews", 5.0))
        self.assertTrue(affirm_score("4.1 (6 reviews)", 4.1))
        self.assertFalse(affirm_score("4.8 (177 reviews)", 5.0))
        # negation awareness
        self.assertFalse(affirms("this is not the Golden Jubilee", "the golden jubilee"))
        self.assertTrue(affirms("Latitudes and also The Golden Jubilee", "the golden jubilee"))
        # counts
        self.assertTrue(contains_count("56 Cruise Results", 56))
        self.assertFalse(contains_count("564 results", 56))


if __name__ == "__main__":
    unittest.main()
