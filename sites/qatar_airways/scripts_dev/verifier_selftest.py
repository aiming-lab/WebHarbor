#!/usr/bin/env python3
"""Offline verifier self-test: synthesise trajectories + DB snapshots and
prove each verifier behaves per the grading contract:

  * no-op run    -> FAIL (navigation/identity gates)
  * correct run  -> PASS (all gates green)
  * shortcut run -> FAIL (right answer, no navigation)

This exercises verify_*.py without a browser, before the real Playwright
walkthroughs, so verifier bugs surface cheaply.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "qatar_airways.db"


def make_run(root: pathlib.Path, task_id: str, steps, answer, mutate=None, suffix=""):
    run = root / (task_id.replace(" ", "_") + suffix)
    (run / "screenshots").mkdir(parents=True)
    traj = {
        "task_id": task_id,
        "start_url": "http://127.0.0.1:43089/",
        "steps": steps,
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
    }
    (run / "trajectory.json").write_text(json.dumps(traj))
    # one decodable 1x1 PNG per referenced screenshot
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKsMIQAAAABJRU5ErkJggg==")
    for s in steps or []:
        name = s.get("screenshot")
        if name:
            (run / "screenshots" / name).write_bytes(png)
    shutil.copyfile(SEED, run / "initial.db")
    shutil.copyfile(SEED, run / "after.db")
    if mutate:
        conn = sqlite3.connect(run / "after.db")
        try:
            for statement in mutate:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()
    return run


def run_verifier(n: int, run_dir: pathlib.Path):
    result = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{n}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"pass": None, "raw": result.stdout[-400:], "err": result.stderr[-400:]}
    return result.returncode, payload


def nav(url, action="navigate", i=[0]):
    i[0] += 1
    return {"action": "navigate", "params": {"url": url},
            "url": url, "url_after": url, "screenshot": f"step_{i[0]:03d}.png"}


def fill(text, i=[100]):
    i[0] += 1
    return {"action": "input", "params": {"text": text}, "screenshot": f"step_{i[0]:03d}.png"}


def steps_for(correct: bool, task: int):
    """The honest navigation path per task (correct=True) or nothing (no-op)."""
    if not correct:
        return [nav("http://127.0.0.1:43089/")]
    common = [
        nav("http://127.0.0.1:43089/"),
    ]
    paths = {
        0: common + [
            nav("http://127.0.0.1:43089/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=2&children=0&cabin=Economy"),
            nav("http://127.0.0.1:43089/en/booking/passenger-details.html?from=DOH&to=LHR&depart=2026-10-08&adults=2&children=0&cabin=Economy&fare=ECO_LITE&flight=7"),
            nav("http://127.0.0.1:43089/en/booking/payment.html"),
            nav("http://127.0.0.1:43089/en/booking/confirmation.html?pnr=AB12CD"),
        ],
        3: common + [
            nav("http://127.0.0.1:43089/en/flight-status.html?mode=number&number=QR004&date=2026-09-24"),
            nav("http://127.0.0.1:43089/en/flight-status.html?mode=route&from=LHR&to=DOH&date=2026-09-24"),
            nav("http://127.0.0.1:43089/en/our-fleet.html"),
            nav("http://127.0.0.1:43089/en/our-fleet/Airbus-A380-800.html"),
        ],
        5: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
            nav("http://127.0.0.1:43089/en/manage-booking.html"),
            nav("http://127.0.0.1:43089/en/manage-booking/QR92XN.html"),
        ],
        7: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/check-in.html"),
            nav("http://127.0.0.1:43089/en/check-in/QC08BV.html"),
            nav("http://127.0.0.1:43089/en/check-in/QC08BV/boarding-pass.html"),
        ],
        8: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/manage-booking/QB55MD.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
        ],
        9: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/avios-calculator.html"),
            fill("JFK"),
        ],
        10: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/membership-tiers.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            fill("bob.c@test.com"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            fill("alice.j@test.com"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
        ],
        11: common + [
            nav("http://127.0.0.1:43089/en/destinations.html?region=themiddleeast"),
            nav("http://127.0.0.1:43089/en/destinations/flights-to-doha.html"),
        ],
        14: common + [
            nav("http://127.0.0.1:43089/en/flight-status.html?mode=route&from=DOH&to=LHR&date=2026-09-24"),
            nav("http://127.0.0.1:43089/en/our-fleet.html"),
            nav("http://127.0.0.1:43089/en/our-fleet/Airbus-A350-900.html"),
            nav("http://127.0.0.1:43089/en/our-fleet/Airbus-A380-800.html"),
        ],
        15: common + [
            nav("http://127.0.0.1:43089/en/baggage.html"),
            nav("http://127.0.0.1:43089/en/help.html?q=carry-on+baggage"),
        ],
        16: common + [nav("http://127.0.0.1:43089/en/help.html?q=hard+of+hearing")],
        1: common + [
            nav("http://127.0.0.1:43089/en/search-results.html?from=DOH&to=BKK&depart=2026-10-12&ret=2026-10-26&adults=1&children=0&cabin=Economy"),
            nav("http://127.0.0.1:43089/en/booking/select-return.html?from=DOH&to=BKK&depart=2026-10-12&ret=2026-10-26&adults=1&children=0&cabin=Economy&fare=ECO_CLASSIC&flight=834"),
            nav("http://127.0.0.1:43089/en/booking/passenger-details.html?from=DOH&to=BKK&depart=2026-10-12&ret=2026-10-26&ret_flight=837&adults=1&children=0&cabin=Economy&fare=ECO_CLASSIC&flight=834"),
            nav("http://127.0.0.1:43089/en/booking/payment.html"),
            nav("http://127.0.0.1:43089/en/booking/confirmation.html?pnr=RS56TU"),
        ],
        2: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/search-results.html?from=DOH&to=CDG&depart=2026-11-02&adults=1&children=0&cabin=Business"),
            nav("http://127.0.0.1:43089/en/booking/passenger-details.html?from=DOH&to=CDG&depart=2026-11-02&adults=1&children=0&cabin=Business&fare=BUS_CLASSIC&flight=41"),
            fill("QRPC0004217"),
            nav("http://127.0.0.1:43089/en/booking/payment.html"),
            nav("http://127.0.0.1:43089/en/booking/confirmation.html?pnr=PC77KD"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
        ],
        4: common + [
            nav("http://127.0.0.1:43089/en/flight-status.html?mode=route&from=DOH&to=SYD&date=2026-09-24"),
            nav("http://127.0.0.1:43089/en/destinations/flights-to-sydney.html"),
        ],
        6: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/baggage.html?fare=First+Elite&route=weight"),
            nav("http://127.0.0.1:43089/en/manage-booking/QD77LW.html"),
        ],
        12: common + [
            nav("http://127.0.0.1:43089/en/destinations/flights-to-tokyo.html"),
            nav("http://127.0.0.1:43089/en/destinations/flights-to-seoul.html"),
        ],
        13: common + [
            nav("http://127.0.0.1:43089/en/offers.html"),
            nav("http://127.0.0.1:43089/en/offers/motogp-adventures.html"),
            nav("http://127.0.0.1:43089/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy&promo=MOTOGP26"),
            nav("http://127.0.0.1:43089/en/booking/passenger-details.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy&fare=ECO_CLASSIC&flight=1&promo=MOTOGP26"),
            nav("http://127.0.0.1:43089/en/booking/payment.html"),
            nav("http://127.0.0.1:43089/en/booking/confirmation.html?pnr=MG44LP"),
        ],
        17: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/join.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/membership-tiers.html"),
        ],
        18: common + [
            nav("http://127.0.0.1:43089/en/Privilege-Club/login.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard/my-profile.html"),
            nav("http://127.0.0.1:43089/en/Privilege-Club/dashboard.html"),
        ],
        19: common + [
            nav("http://127.0.0.1:43089/en/search-results.html?from=DOH&to=DXB&depart=2026-10-05&adults=2&children=0&cabin=Economy"),
            nav("http://127.0.0.1:43089/en/booking/passenger-details.html?from=DOH&to=DXB&depart=2026-10-05&adults=2&children=0&cabin=Economy&fare=ECO_LITE&flight=1002"),
            nav("http://127.0.0.1:43089/en/booking/payment.html"),
            nav("http://127.0.0.1:43089/en/booking/confirmation.html?pnr=DX88NB"),
        ],
    }
    return paths.get(task)


# ---------------------------------------------------------------- correct-run mutations + answers
CORRECT = {
    0: ("Booked the cheapest Economy Lite flight QR007 for John and Mary Smith. "
        "Booking reference AB12CD. Total charged USD 1,490.",
        ["INSERT INTO bookings (pnr, contact_email, contact_last_name, cabin, fare_type,"
         " adults, children, extra_bags, total_paid, avios_redeemed, promo_code,"
         " card_last4, status, checked_in, created_at)"
         " VALUES ('AB12CD','john.smith@example.com','Smith','Economy','ECO_LITE',2,0,0,"
         "1490,0,NULL,'9010','confirmed',0,'2026-09-24')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='AB12CD'), 7, 'DOH', 'LHR',"
         " '2026-10-08', '08:50', '14:25', '359', 5215, 1330, 0, 'B02')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='AB12CD'),"
         " 'Mr','John','Smith','adult','157-0000000001')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='AB12CD'),"
         " 'Mrs','Mary','Smith','adult','157-0000000002')"]),
    3: ("QR004 on 24 September 2026 is En route. Scheduled departure 15:05, estimated "
        "arrival 23:47, operated by the Airbus A380-800, which offers First, Business "
        "and Economy cabins and seats 517 passengers in total. The earliest London to "
        "Doha flight that day is QR104, departing 08:25.", None),
    5: ("Cancelled my Paris trip QR92XN (QR041 Doha to Paris on 2 November 2026). The "
        "cancellation message said the booking was cancelled and the refund is "
        "processed to the original payment method. My other trips are unchanged.",
        ["UPDATE bookings SET status='cancelled' WHERE pnr='QR92XN'"]),
    7: ("Checked in QC08BV: Carol Davis 30A, James Davis 30B. Boarding gate F22, "
        "boarding time 07:20, seat fees USD 60.",
        ["UPDATE bookings SET checked_in=1, total_paid=6847 WHERE pnr='QC08BV'",
         "UPDATE passengers SET seat_out='30A' WHERE id IN (SELECT id FROM passengers"
         " WHERE booking_id=(SELECT id FROM bookings WHERE pnr='QC08BV') AND first_name='Carol')",
         "UPDATE passengers SET seat_out='30B' WHERE id IN (SELECT id FROM passengers"
         " WHERE booking_id=(SELECT id FROM bookings WHERE pnr='QC08BV') AND first_name='James')"]),
    8: ("Upgraded QB55MD to Business Class with 1,948 Avios; the booking page showed "
        "my balance of 15,300 before the upgrade. The booking now shows Business Class. "
        "My dashboard shows an Avios balance of 13,352 and a recent activity entry: "
        "Upgrade to Business Class on QR826 (DOH->BKK), -1,948 Avios.",
        ["UPDATE bookings SET cabin='Business', avios_redeemed=1948 WHERE pnr='QB55MD'",
         "UPDATE users SET avios=13352 WHERE email='bob.c@test.com'",
         "INSERT INTO activities (user_id, kind, avios, qpoints, description, occurred_at)"
         " VALUES (2,'redeem',-1948,0,'Upgrade to Business Class','2026-09-24')"]),
    9: ("A one-way Business Class flight Doha to New York JFK earns a Gold member "
        "3,766 Avios and 431 Qpoints. The calculator used flight QR701 departing 08:00.",
        None),
    10: ("320 Qpoints qualifies for Gold tier, which carries oneworld Sapphire status. "
         "The next tier up, Platinum, needs 600 Qpoints within 12 months. Gold gives "
         "20kg extra checked baggage (or one piece). Bob holds Silver and needs 90 more "
         "Qpoints for Gold; Alice holds Gold and needs 185 more Qpoints for Platinum. "
         "Bob is the closest of the three of us to the next tier.", None),
    11: ("The city is Doha: its Things to do mentions the Museum of Islamic Art. Two "
         "activities from its Activities section: a stroll along the Corniche and a "
         "dhow boat ride, plus a visit to The Pearl island.", None),
    14: ("QR105 is operated by the Airbus A350-900, which features Qsuite and seats "
         "283 passengers; its Business Class cabin spans rows 1-8 and its Economy "
         "cabin rows 30-51. The largest aircraft in the fleet is the Airbus A380-800; "
         "its First Class cabin spans rows 1-3.", None),
    15: ("Economy Comfort on the Doha-Sao Paulo piece-concept route includes 2 pieces "
         "up to 23kg each. Each extra 23kg piece costs USD 140 on this route. Business "
         "Elite includes 40kg on weight-concept routes. Economy Lite includes 1 piece "
         "up to 23kg on piece-concept routes. Economy carry-on is 1 piece up to 7kg.", None),
    16: ("The dedicated hard-of-hearing support number is +1 833 607 2675. The medical "
         "assistance form must be submitted at least 48 hours before departure (and up "
         "to 7 days before). Firearms for Oman must be requested more than 19 days "
         "prior to departure. Proof-of-travel certificates can be requested for up to "
         "12 months from the date of travel. Infants can carry one baby stroller or "
         "collapsible carrycot at no additional cost.", None),
    1: ("Booked the earliest flights: QR834 out on 12 October and QR837 back on "
        "26 October, Economy Classic. Booking reference RS56TU. Total charged USD 1,814.",
        ["INSERT INTO bookings (pnr, contact_email, contact_last_name, cabin, fare_type,"
         " adults, children, extra_bags, total_paid, avios_redeemed, promo_code,"
         " card_last4, status, checked_in, created_at)"
         " VALUES ('RS56TU','sarah.chen@example.com','Chen','Economy','ECO_CLASSIC',1,0,0,"
         "1814,0,NULL,'7890','confirmed',0,'2026-09-24')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='RS56TU'), 834, 'DOH', 'BKK',"
         " '2026-10-12', '02:00', '12:30', '388', 5260, 810, 0, 'E35')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='RS56TU'), 837, 'BKK', 'DOH',"
         " '2026-10-26', '02:30', '06:10', '388', 5260, 810, 0, 'A18')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='RS56TU'),"
         " 'Ms','Sarah','Chen','adult','157-0000000003')"]),
    2: ("Booked Business Classic Doha to Paris on QR041 for 2 November 2026. Booking "
        "reference PC77KD, total charged USD 8,915. My Avios balance is now 49,990.",
        ["INSERT INTO bookings (pnr, user_id, pc_number, contact_email, contact_last_name,"
         " cabin, fare_type, adults, children, extra_bags, total_paid, avios_redeemed,"
         " promo_code, card_last4, status, checked_in, created_at)"
         " VALUES ('PC77KD', 1, 'QRPC0004217', 'alice.j@test.com', 'Johnson',"
         " 'Business', 'BUS_CLASSIC', 1, 0, 0, 8915, 0, NULL, '4242', 'confirmed', 0,"
         " '2026-09-24')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='PC77KD'), 41, 'DOH', 'CDG',"
         " '2026-11-02', '01:25', '07:00', '388', 4974, 7960, 0, 'A02')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='PC77KD'),"
         " 'Ms','Alice','Johnson','adult','157-0000000004')",
         "UPDATE users SET avios=49990 WHERE email='alice.j@test.com'",
         "INSERT INTO activities (user_id, kind, avios, qpoints, description, occurred_at)"
         " VALUES (1, 'earn', 1740, 199, 'Flight QR041 DOH->CDG (Business Classic)',"
         " '2026-09-24')"]),
    4: ("QR908 flies nonstop from Doha to Sydney on a Boeing 777-300ER, departing "
        "20:05. The Sydney guide's Things to do starts with the Sydney Opera House.",
        None),
    6: ("First Elite includes 50kg of checked baggage on weight-concept routes. I added "
        "two extra 23kg baggage pieces to QD77LW at USD 140 per piece; the fee charged "
        "was USD 280 and the new total shown on the booking is USD 69,731.",
        ["UPDATE bookings SET extra_bags=2, total_paid=69731 WHERE pnr='QD77LW'"]),
    12: ("Tokyo's Activities section mentions the Yayoi Kusama Museum. Seoul's "
         "Activities section says the Seoul City Wall Trail that the Naksan Section is "
         "part of stretches 18.6 kilometres and suggests staying in Bukchon Hanok "
         "Village; its Things to do highlights Changdeokgung, a Joseon dynasty palace "
         "with a Secret Garden. Tokyo's Food section says you can sample amazing sushi "
         "at the Tsukiji Outer Market, and its Activities section calls Yoyogi Park "
         "perfect for jogging and picnics.", None),
    13: ("Promo code MOTOGP26 applied a discount of USD 79. Booking reference MG44LP, "
         "total charged USD 796.",
        ["INSERT INTO bookings (pnr, contact_email, contact_last_name, cabin, fare_type,"
         " adults, children, extra_bags, total_paid, avios_redeemed, promo_code,"
         " card_last4, status, checked_in, created_at)"
         " VALUES ('MG44LP','leo.martin@example.com','Martin','Economy','ECO_CLASSIC',"
         "1,0,0,796,0,'MOTOGP26','5556','confirmed',0,'2026-09-24')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='MG44LP'), 1, 'DOH', 'LHR',"
         " '2026-10-08', '12:40', '18:00', '351', 5215, 790, 0, 'B02')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='MG44LP'),"
         " 'Mr','Leo','Martin','adult','157-0000000005')"]),
    17: ("My new membership number is QRPC0000512, starting tier Burgundy, which saves "
         "10% on seat selection. It takes 150 Qpoints within 12 months to upgrade to "
         "Silver. My account shows I joined on 2026-09-24.",
        ["INSERT INTO users (email, password_hash, title, first_name, last_name, tier,"
         " avios, qpoints, qcredits, membership_no, country, mobile, joined)"
         " VALUES ('fiona.gray@example.com','pbkdf2:sha256:1000000$x$f','Ms','Fiona',"
         "'Gray','Burgundy',0,0,0,'QRPC0000512','Ireland','+353 86 123 4567','2026-09-24')"]),
    18: ("Your profile has been updated: country Brazil, mobile +55 11 98765 4321. The "
         "profile still shows Carol Davis, carol.d@test.com, tier Burgundy, Avios 4,200 "
         "and Qpoints 60. The most recent entry in my recent activity is the Privilege "
         "Club partner bonus (Qatar Duty Free) of +2,500 Avios.",
        ["UPDATE users SET country='Brazil', mobile='+55 11 98765 4321'"
         " WHERE email='carol.d@test.com'"]),
    19: ("Economy Lite totals USD 280 for two passengers and Economy Comfort totals "
         "USD 430. I booked the cheaper Economy Lite for Ravi Patel and Anaya Patel; "
         "booking reference DX88NB, total charged USD 314.",
        ["INSERT INTO bookings (pnr, contact_email, contact_last_name, cabin, fare_type,"
         " adults, children, extra_bags, total_paid, avios_redeemed, promo_code,"
         " card_last4, status, checked_in, created_at)"
         " VALUES ('DX88NB','ravi.patel@example.com','Patel','Economy','ECO_LITE',2,0,0,"
         "314,0,NULL,'4444','confirmed',0,'2026-09-24')",
         "INSERT INTO booking_legs (booking_id, flight_number, origin_code, dest_code,"
         " leg_date, dep_time, arr_time, equipment, distance_km, fare_price, seat_fee, gate)"
         " VALUES ((SELECT id FROM bookings WHERE pnr='DX88NB'), 1002, 'DOH', 'DXB',"
         " '2026-10-05', '01:05', '03:20', '77W', 379, 280, 0, 'B11')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='DX88NB'),"
         " 'Mr','Ravi','Patel','adult','157-0000000006')",
         "INSERT INTO passengers (booking_id, title, first_name, last_name, pax_type,"
         " ticket_number) VALUES ((SELECT id FROM bookings WHERE pnr='DX88NB'),"
         " 'Ms','Anaya','Patel','adult','157-0000000007')"]),
}


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="qa-verify-selftest-"))
    failures = []
    for task, (answer, mutate) in CORRECT.items():
        # correct run
        run = make_run(tmp, f"Qatar Airways--{task}", steps_for(True, task), answer, mutate, suffix="-correct")
        rc, payload = run_verifier(task, run)
        if rc != 0 or not payload.get("pass"):
            failures.append((task, "correct-run", payload.get("reason"), payload))
        # no-op run: no navigation, empty answer
        run = make_run(tmp, f"Qatar Airways--{task}", [], "", suffix="-noop")
        rc, payload = run_verifier(task, run)
        if rc == 0 or payload.get("pass"):
            failures.append((task, "noop-run", "expected FAIL", payload))
        # shortcut run: correct answer, no navigation, read-only DB
        run = make_run(tmp, f"Qatar Airways--{task}", [nav("http://127.0.0.1:43089/")], answer, suffix="-shortcut")
        rc, payload = run_verifier(task, run)
        if rc == 0 or payload.get("pass"):
            failures.append((task, "shortcut-run", "expected FAIL", payload))
        print(f"task {task}: correct={'PASS' if rc is not None else '?'} checked")

    if failures:
        print("\nFAILURES:")
        for task, kind, reason, payload in failures:
            print(f"  task {task} {kind}: {reason}")
            print("   ", json.dumps(payload, ensure_ascii=False)[:600])
        return 1
    print("\nall verifier self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
