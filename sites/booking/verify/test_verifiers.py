#!/usr/bin/env python3
"""Grading-control suite for the Booking verifiers.

For every task (Booking--0 .. Booking--43):
  * POSITIVE: a synthetic run package with the task's natural navigation and a
    factually correct final answer must PASS (booking tasks use a synthetic
    after-DB carrying the invited cart/booking row).
  * NO-OP: homepage-only steps + empty answer must FAIL.
  * SHORTCUT: the correct answer with homepage-only navigation must FAIL.
  * WRONG-ANSWER: the task's navigation with a plausible-but-wrong answer must FAIL.
  * FOREIGN-TASK-ID: a trajectory stamped with another task id must FAIL.
  * MISSING-TRAJECTORY / MISSING-SCREENSHOT: broken run packages must FAIL.
  * DB-WRITE: a mutated after-DB must FAIL.

Plus tasks.jsonl contract checks: 44 rows, exact key set, no `answer` key,
verifier files exist, non-empty rubrics, and the five original fields
byte-identical to the pre-update evidence copy.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]          # .../build/booking (worktree root)
SITE = REPO / 'sites/booking'
VER = SITE / 'verify'
AGENT_DEMO = REPO / 'agent_demo'
VENV_PY = AGENT_DEMO / '.venv/bin/python'
SEED_DB = Path('/data/zhaoyang-user-projects/websyn/WebHarbor/sites/booking/instance_seed/booking.db')
EVID = Path('/data/zhaoyang-user-projects/websyn/_wh_review_tools/orch/verify/reports/booking/taskfile-evidence')
SHOT = Path('/data/zhaoyang-user-projects/websyn/_wh_review_tools/orch/verify/reports/booking/audit/task_09/search.png')
ORIGIN = "http://localhost:41005/"

BOOKING_TASKS = {6: (109, "2024-01-22", "2024-01-25"),      # Luskin Hotel
                 11: (233, "2024-03-20", "2024-03-27"),     # The Peninsula Chicago
                 13: (185, "2024-02-14", "2024-02-21"),     # Le Marais Suites
                 14: (275, "2024-03-03", "2024-03-05")}     # Melia Paris Louvre

# ---------------------------------------------------------------- acceptor probes (rework D1/D2)
# The independent acceptor's adversarial probe packages (reports/booking/runs/acc/
# probes/), reproduced verbatim as synthetic packages: the same navigation, the
# same task ids and the same final answers. Each probe states the RIGHT entity
# with the required fact DENIED ("... not 3", "no deal", "does not include
# breakfast", "... , not Booking Holdings") and must FAIL: the count helper is
# polarity-aware and the mention checks require an AFFIRMATIVE occurrence.
NEGATION_PROBES = {
    "p1": (30, ["/search?q=London&breakfast=1&gym=1"],
           "After applying the Breakfast included and Fitness center filters, 5 properties are left, not 3."),
    "q1": (30, ["/search?q=London&breakfast=1&gym=1"],
           "Applying both filters leaves 6 options available, though some say 3."),
    "p4": (32, ["/search?q=Sydney&pool=1&airport_shuttle=1"],
           "With the Swimming Pool and Airport Shuttle filters applied, 4 hotels are available, not 3."),
    "q2": (32, ["/search?q=Sydney&pool=1&airport_shuttle=1"],
           "Only 2 results are available; definitely not 3 hotels."),
    "r0": (0, ["/search?q=Mexico&checkin=2025-12-25&checkout=2025-12-26",
                "/property/st-regis-mexico-city-mexico-city"],
           "St. Regis Mexico City has no deal and no discount for December 25-26; it costs $209 per night."),
    "r4": (4, ["/search?q=Kashi+Vishwanath+Temple&breakfast=1"],
           "Kashi Vishwanath Guest House is the cheapest at $37 but it does not include breakfast."),
    "r5": (5, ["/search?q=Bali&wifi=1&air_conditioning=1"],
           "Four Seasons Sayan in Bali has no free WiFi and no air conditioning."),
    "r22": (22, ["/search?q=Amsterdam"],
            "Tribe Amsterdam City is rated 9.3 and does not offer bicycle rental."),
    "r28": (28, ["/search?q=Dubai"],
            "Atlantis The Palm in Dubai has no swimming pool for the week-long stay."),
    "r39": (39, ["/search?q=Toronto&pet_friendly=1&parking=1"],
            "Four Seasons Hotel Toronto allows no pets and has no parking."),
    "q3": (41, ["/", "/about"],
            "Booking.com belongs to Expedia Group, not Booking Holdings."),
}

# the first check each probe must now FAIL on (verifier check names)
PROBE_EXPECT_REASON = {"p1": "answer_count", "q1": "answer_count", "p4": "answer_count",
                       "q2": "answer_count", "r0": "answer_states_the_deal",
                       "r4": "answer_mentions_breakfast", "r5": "answer_mentions_wifi_and_ac",
                       "r22": "answer_mentions_bicycle", "r28": "answer_mentions_pool",
                       "r39": "answer_mentions_pet_and_parking", "q3": "answer_parent_company"}

# legitimate affirmative phrasings (incl. the 'not only' idiom and negations in
# OTHER clauses) that must keep PASSing after the negation guards -- regression
# guard against over-blocking.
AFFIRMATIVE_GUARDS = {
    0: (["/search?q=Mexico&checkin=2024-12-25&checkout=2024-12-26",
         "/property/polanco-boutique-hotel-mexico-city"],
        "Not only does the Polanco Boutique Hotel have a Genius deal, it is the cheapest deal in Mexico City at $122 per night."),
    4: (["/search?q=Kashi+Vishwanath+Temple&breakfast=1"],
        "Breakfast is included at the Kashi Vishwanath Guest House, which costs $37 per night."),
    28: (["/search?q=Dubai"],
         "The Lana - Dorchester Collection has a swimming pool; not every Dubai hotel does."),
    30: (["/search?q=London&breakfast=1&gym=1"],
         "There are exactly 3 properties left after applying the Breakfast included and Fitness center filters."),
    32: (["/search?q=Sydney&pool=1&airport_shuttle=1"],
         "The filters leave 3 hotels available, with a pool and an airport shuttle for each."),
    41: (["/", "/about"],
         "Booking.com belongs to Booking Holdings Inc. (NASDAQ: BKNG), not to Expedia Group."),
}

# ---------------------------------------------------------------- positives
P = {}
P[0] = ([f"{ORIGIN}search?q=Mexico&checkin=2024-12-25&checkout=2024-12-26",
         f"{ORIGIN}property/polanco-boutique-hotel-mexico-city"],
        "Polanco Boutique Hotel in Mexico City has a deal for December 25-26: 25% off, $121 per night (a Genius deal).")
P[1] = ([f"{ORIGIN}search?q=Jakarta&sort=price_asc&checkin=2024-01-01&checkout=2024-01-04&adults=2",
         f"{ORIGIN}property/reddoorz-plus-menteng-jakarta"],
        "The cheapest available hotel room in Jakarta for the three-night stay is the Standard Double Room at RedDoorz Plus Menteng — $66 per night, $198 for the three nights.")
P[2] = ([f"{ORIGIN}search?q=Ohio&adults=3&rooms=2&checkin=2024-12-20&checkout=2024-12-23"],
        "Hilton Columbus Downtown in Ohio works for 3 adults and 2 rooms for the December 20-23 stay ($141/night).")
P[3] = ([f"{ORIGIN}search?q=Los+Angeles&min_stars=4&checkin=2024-12-18&checkout=2024-12-21"],
        "Conrad Los Angeles is a 5-star hotel in Los Angeles available for the December 18 stay ($256/night).")
P[4] = ([f"{ORIGIN}search?q=Kashi+Vishwanath+Temple&breakfast=1&checkin=2024-12-25&checkout=2024-12-26"],
        "The cheapest hotel near Kashi Vishwanath Temple that offers breakfast is the Kashi Vishwanath Guest House at $37 per night (30% off), with breakfast included.")
P[5] = ([f"{ORIGIN}search?q=Bali&wifi=1&air_conditioning=1&checkin=2024-01-01&checkout=2024-01-04"],
        "Four Seasons Sayan in Bali has free WiFi and air conditioning for the January 1-4 stay ($232/night).")
P[6] = ([f"{ORIGIN}search?q=Los+Angeles&breakfast=1&airport_shuttle=1&checkin=2024-01-22&checkout=2024-01-25",
         f"{ORIGIN}property/luskin-hotel-los-angeles?checkin=2024-01-22&checkout=2024-01-25",
         f"{ORIGIN}bag"],
        "I booked one room at the Luskin Hotel in Los Angeles (breakfast included, airport shuttle) for January 22-25; the reservation is in my bag.")
P[7] = ([f"{ORIGIN}search?q=National+University+of+Singapore&checkin=2024-01-03&checkout=2024-01-06"],
        "The Fullerton Hotel Singapore is the closest to the National University of Singapore at 2.4 miles, and at $349 per night it costs less than $500.")
P[8] = ([f"{ORIGIN}search?q=Chennai&free_cancellation=1&checkin=2023-12-20&checkout=2023-12-21"],
        "Park Hyatt Chennai has the highest review score among Chennai hotels with free cancellation: 9.6.")
P[9] = ([f"{ORIGIN}search?q=London&max_price=250&adults=2&checkin=2024-12-25&checkout=2024-12-29"],
        "Three London options under $250 per night: room2 London Chiswick Hometel ($142), art'otel London Hoxton ($177), and nhow London ($163).")
P[10] = ([f"{ORIGIN}search?q=Paris&free_cancellation=1&adults=2&checkin=2024-02-14&checkout=2024-02-21"],
         "Le Marais Suites in Paris is well reviewed (9.4) and offers free cancellation for the February 14-21 week.")
P[11] = ([f"{ORIGIN}search?q=downtown+Chicago&min_rating=9&free_cancellation=1&gym=1&checkin=2024-03-20&checkout=2024-03-27",
          f"{ORIGIN}property/the-peninsula-chicago-chicago?checkin=2024-03-20&checkout=2024-03-27",
          f"{ORIGIN}bag"],
         "I reserved The Peninsula Chicago (rating 9.1, free cancellation, fitness center) for March 20-27.")
P[12] = ([f"{ORIGIN}search?q=Paris&min_rating=8&wifi=1&checkin=2024-01-05&checkout=2024-01-10"],
         "Melia Paris Louvre is rated 9.1 and has free WiFi, available for the five-night stay from January 5.")
P[13] = ([f"{ORIGIN}search?q=Paris&adults=2&children=2&free_cancellation=1&checkin=2024-02-14&checkout=2024-02-21",
          f"{ORIGIN}property/le-marais-suites-paris?checkin=2024-02-14&checkout=2024-02-21",
          f"{ORIGIN}bag"],
         "I booked Le Marais Suites in Paris for the family of four (two adults, two children) for February 14-21; it offers free cancellation.")
P[14] = ([f"{ORIGIN}search?q=Louvre&pool=1&wifi=1&checkin=2024-03-03&checkout=2024-03-05",
          f"{ORIGIN}property/melia-paris-louvre-paris?checkin=2024-03-03&checkout=2024-03-05",
          f"{ORIGIN}bag"],
         "I booked Melia Paris Louvre, a highly-rated hotel near the Louvre with a swimming pool and free WiFi, for the March 3-5 weekend.")
P[15] = ([f"{ORIGIN}search?q=Rome&min_stars=5&checkin=2024-01-10&checkout=2024-01-20&adults=2",
          f"{ORIGIN}property/hotel-de-russie-rome"],
         "Hotel de Russie is the highest-rated luxury hotel in Rome: it costs $304 per night, is rated 8.6, and offers a spa & wellness, fitness center, restaurant and swimming pool.")
P[16] = ([f"{ORIGIN}search?q=Paris&min_rating=9&wifi=1&breakfast=1&checkin=2024-01-15&checkout=2024-01-20"],
         "1.75 Paris Le Charme, located in the 13th arr., is rated 9.1 with free WiFi and breakfast included, at $229 per night.")
P[17] = ([f"{ORIGIN}search?q=Paris&gym=1&min_rating=8&sort=review_score_desc&checkin=2024-02-14&checkout=2024-02-19"],
         "Sorted by best reviewed, the top option is Too Hotel & Spa Paris - MGallery Collection (9.6), which has a fitness center.")
P[18] = ([f"{ORIGIN}search?q=London&min_rating=8&checkin=2024-02-14&checkout=2024-02-21&adults=2"],
         "Claridge's in London is rated 9.3 — an iconic Mayfair hotel with elegant rooms and impeccable service, perfect for a couple.")
P[19] = ([f"{ORIGIN}search?q=Paris&min_rating=8&sort=review_score_desc&checkin=2024-03-18&checkout=2024-03-20"],
         "Top three Paris hotels by user reviews: Too Hotel & Spa Paris - MGallery Collection (9.6), Le Marais Suites (9.4), and Quinzerie hôtel (9.3).")
P[20] = ([f"{ORIGIN}search?q=Rome&min_rating=7&free_cancellation=1&breakfast=1&checkin=2024-02-28&checkout=2024-03-02&adults=2"],
         "Hotel Grifo Rome (9.2) offers free cancellation and breakfast included for the February 28 - March 2 stay.")
P[21] = ([f"{ORIGIN}search?q=Sydney&min_rating=8&wifi=1&parking=1&checkin=2024-03-10&checkout=2024-03-14"],
         "Paramount House Hotel in Sydney is rated 9.4 and offers free WiFi and parking for the four-night stay.")
P[22] = ([f"{ORIGIN}search?q=Amsterdam&min_rating=9&bicycle=1&checkin=2024-03-15&checkout=2024-03-22&adults=2"],
         "Tribe Amsterdam City is rated 9.3 and offers bicycle rental for the week-long stay.")
P[23] = ([f"{ORIGIN}search?q=Tokyo&min_rating=9&spa=1&checkin=2024-02-20&checkout=2024-02-25",
          f"{ORIGIN}property/mercure-tokyo-haneda-airport-tokyo"],
         "Mercure Tokyo Haneda Airport has a spa and wellness center and is rated 9.4. Free cancellation is offered for this property.")
P[24] = ([f"{ORIGIN}search?q=Barcelona&wifi=1&breakfast=1&sort=distance_beach&checkin=2024-02-25&checkout=2024-02-28"],
         "Sorted by distance from the beach, Praktik Èssens is 0.8 miles from Barceloneta Beach and offers free WiFi and breakfast included.")
P[25] = ([f"{ORIGIN}search?q=Lisbon&min_rating=8.5&airport_shuttle=1&breakfast=1&checkin=2024-03-01&checkout=2024-03-07&adults=2"],
         "Pestana Palace Lisbon (9.4) offers an airport shuttle and breakfast included for the six-night stay.")
P[26] = ([f"{ORIGIN}search?q=Paris&min_stars=3&min_rating=8&parking=1&checkin=2024-02-20&checkout=2024-02-23"],
         "Drawing House in Paris is a 3-star property rated 8.9 with parking available.")
P[27] = ([f"{ORIGIN}search?q=Melbourne&parking=1&wifi=1&checkin=2024-02-28&checkout=2024-03-04"],
         "The Langham Melbourne (9.0) offers free parking and free WiFi for the February 28 - March 4 stay.")
P[28] = ([f"{ORIGIN}search?q=Dubai&pool=1&checkin=2024-02-22&checkout=2024-02-29"],
         "Atlantis The Palm in Dubai has a swimming pool for the week-long February 22-29 stay.")
P[29] = ([f"{ORIGIN}search?q=Toronto&gym=1&min_rating=8&checkin=2024-03-05&checkout=2024-03-07"],
         "Chelsea Hotel Toronto (9.5) has a fitness center and an 8+ rating for the two-night stay.")
P[30] = ([f"{ORIGIN}search?q=London&breakfast=1&gym=1&checkin=2024-03-20&checkout=2024-03-23"],
         "After applying the Breakfast included and Fitness center filters, 3 properties are left.")
P[31] = ([f"{ORIGIN}search?q=Rio+de+Janeiro&checkin=2024-03-01&checkout=2024-03-07"],
         "The Brands filter shows Hilton with the most hotels (4) and Accor with the fewest (2).")
P[32] = ([f"{ORIGIN}search?q=Sydney&pool=1&airport_shuttle=1&checkin=2024-02-24&checkout=2024-02-27"],
         "With the Swimming Pool and Airport Shuttle filters applied, the total number of hotels available is 3.")
P[33] = ([f"{ORIGIN}help"],
         "You will receive a cancellation confirmation email, and the booking status in My bookings changes to Cancelled.")
P[34] = ([f"{ORIGIN}search?q=Berlin&checkin=2024-03-15&checkout=2024-03-18&adults=1",
          f"{ORIGIN}property/the-charming-by-curt-suites-berlin"],
         "The Charming by Curt Suites in Berlin costs $77 per night, so the three-night stay is about $231 (¥557 per night, roughly ¥1671 for three nights in CNY).")
P[35] = ([f"{ORIGIN}articles", f"{ORIGIN}articles/top-5-european-cities-food-lovers"],
         "The article 'Top 5 European Cities for Food Lovers' covers Paris, Rome, Lisbon, Barcelona and Vienna as its five destinations.")
P[36] = ([f"{ORIGIN}search?q=Rome&max_price=100&sort=price_asc&adults=1&checkin=2024-03-20&checkout=2024-03-23"],
         "Sorted by price, the top three cheapest Rome hotels under $100 are Hostel Roma Termini ($34), Hotel Dina Rome ($58), and Pensione Roma Centro ($61) — none of them offers breakfast.")
P[37] = ([f"{ORIGIN}search?q=Bali&checkin=2024-03-20&checkout=2024-03-25",
          f"{ORIGIN}property/the-udaya-resort-ubud-bali"],
         "The Udaya Resort Ubud in Bali — a resort, not a hotel — is available for the March 20-25 dates; it provides a spa & wellness center, a swimming pool, a restaurant and beachfront access.")
P[38] = ([f"{ORIGIN}search?q=Vienna&parking=1&breakfast=1&min_rating=8&checkin=2024-02-28&checkout=2024-03-04"],
         "Hotel Josefine in Vienna (9.1) offers parking and breakfast included for the 4-night stay.")
P[39] = ([f"{ORIGIN}search?q=Toronto&pet_friendly=1&parking=1&checkin=2024-02-24&checkout=2024-02-26"],
         "Fairmont Royal York Toronto is pet-friendly and has parking available for the February 24-26 stay.")
P[40] = ([f"{ORIGIN}search?q=Shenzhen&currency=CNY&checkin=2024-03-06&checkout=2024-03-08"],
         "CitiGO Shenzhen converts to ¥612 CNY per night on the page for the March 6-8 stay.")
P[41] = ([f"{ORIGIN}", f"{ORIGIN}about"],
         "Booking.com is part of Booking Holdings Inc. (NASDAQ: BKNG).")
P[42] = ([f"{ORIGIN}search?q=Hokkaido&min_rating=9&checkin=2024-03-01&checkout=2024-03-07",
          f"{ORIGIN}property/jr-tower-hotel-nikko-sapporo-sapporo"],
         "JR Tower Hotel Nikko Sapporo is rated 9.2. Categories above 9: Cleanliness (9.3), Comfort (9.0), Staff (9.4), Location (9.2), Free WiFi (9.0). Categories below 9: Facilities (8.7), Value for money (8.6).")
P[43] = ([f"{ORIGIN}search?q=Los+Angeles&checkin=2024-05-01&checkout=2024-05-03"],
         "The results page offers filters like Free cancellation, Breakfast included, Free WiFi, Swimming pool, Parking, Fitness center, star rating, review score, brand and sort options.")

WRONG = {
    0: "Camino Real Aeropuerto in Mexico City has a great deal for December 25-26.",
    1: "The cheapest hotel room in Jakarta is the Standard Room at Artotel Thamrin Jakarta, $94 per night.",
    2: "21c Museum Hotel Cincinnati in Ohio is perfect for the stay.",
    3: "STAY OPEN Venice Beach is a 3-star hotel in Los Angeles for the December stay.",
    4: "Taj Nadesar Palace is the cheapest hotel near Kashi Vishwanath Temple with breakfast, at $244 per night.",
    5: "Alila Seminyak in Bali has free WiFi and air conditioning for the January 1-4 stay.",
    6: "I booked one room at the Hilton LAX in Los Angeles for January 22-25.",
    7: "The Clan Hotel Singapore by Far East Hospitality is the closest to the National University of Singapore at 3.0 miles, well under $500.",
    8: "The Raintree Hotel Chennai has the highest review score with free cancellation, at 9.4.",
    9: "Two options under $250: room2 London Chiswick Hometel and art'otel London Hoxton.",
    10: "SO/ Paris Hotel is well reviewed (8.7) and offers free cancellation for the February 14-21 week.",
    11: "I reserved the Hyatt Regency Chicago (rating 9.1, free cancellation, fitness center) for March 20-27.",
    12: "Les Rives Oceanik in Paris is rated 8.5 and has free WiFi for the five-night stay.",
    13: "I booked Too Hotel & Spa Paris - MGallery Collection for the family of four (two adults, two children) for February 14-21, with free cancellation.",
    14: "I booked Too Hotel & Spa Paris - MGallery Collection with its pool and free WiFi near the Louvre for March 3-5.",
    15: "Hotel Eden is the highest-rated luxury hotel in Rome: $229 per night, rated 8.0, with a restaurant.",
    16: "Hôtel Le Milie Rose in the 10th arr. is rated 8.6 with free WiFi and breakfast, at $118 per night.",
    17: "Sorted by best reviewed, the top option is Les Rives Oceanik (8.5), which has a fitness center.",
    18: "Park Plaza Westminster Bridge is a nice London hotel.",
    19: "Top three Paris hotels by user reviews: Too Hotel & Spa Paris (9.6), Hôtel La Canopée (9.0), and Hotel Le Louvre Paris (9.0).",
    20: "Hotel Eden in Rome (8.0) offers free cancellation and breakfast included for the February 28 - March 2 stay.",
    21: "The Langham Melbourne (9.0) offers free WiFi and parking in Sydney for the four-night stay.",
    22: "The July - Boat & Co in Amsterdam is rated 9.4 and offers bicycle rental for the week-long stay.",
    23: "lyf Shibuya Tokyo has a spa and wellness center, rated 9.0. Free cancellation is offered for this property.",
    24: "Sorted by distance from the beach, H10 Madison 4* Sup is close to Barceloneta Beach and offers free WiFi and breakfast included.",
    25: "Hotel Avenida Palace Lisbon (8.7) offers an airport shuttle and breakfast included for the six-night stay.",
    26: "Melia Paris Louvre is a 4-star Paris hotel rated 9.1 with parking.",
    27: "Park Hyatt Melbourne (9.0) offers free parking and free WiFi for the February 28 - March 4 stay.",
    28: "Casa Camper Berlin has a swimming pool for the week-long stay.",
    29: "Ace Hotel Toronto (8.7) has a fitness center and an 8+ rating for the two-night stay.",
    30: "After applying the Breakfast included and Fitness center filters, 5 properties are left.",
    31: "The Brands filter shows Marriott with the most hotels (3) and Accor with the fewest (2).",
    32: "With the Swimming Pool and Airport Shuttle filters applied, 4 hotels are available in total.",
    33: "Your booking is cancelled automatically when the hotel confirms payment.",
    34: "The Charming by Curt Suites in Berlin costs $77 per night and ¥700 CNY per night for the three-night stay.",
    35: "The article covers Paris and Rome as its main destinations.",
    36: "Yes, the top three cheapest Rome hotels under $100 all include breakfast.",
    37: "Grandmas Plus Hotel Airport in Bali is available for March 20-25 with free WiFi and air conditioning.",
    38: "Jaz in the City Vienna (9.0) has parking and breakfast included for the 4-night stay.",
    39: "Chelsea Hotel Toronto is pet-friendly and has parking available for the stay.",
    40: "CitiGO Shenzhen converts to ¥700 CNY per night on the page.",
    41: "Booking.com belongs to Expedia Group.",
    42: "JR Tower Hotel Nikko Sapporo: categories above 9 are Facilities and Value for money; below 9 are Cleanliness and Staff.",
    43: "The results page lets you sort and filter.",
}

# ---------------------------------------------------------------- helpers
WORK = Path(tempfile.mkdtemp(prefix="wh_bk_tests_"))


_COUNTER = [0]


def build_run(task, urls, answer, task_id=None, shots=True, with_traj=True):
    _COUNTER[0] += 1
    d = WORK / f"t{task}_{_COUNTER[0]}"
    if d.exists():
        shutil.rmtree(d)
    (d / 'screenshots').mkdir(parents=True)
    if shots:
        shutil.copy2(SHOT, d / 'screenshots' / 'step_000.png')
    steps = []
    for i, u in enumerate(urls):
        steps.append({"step": i, "url": u, "url_after": u, "title": "x", "thought": "",
                      "action": "navigate", "params": {},
                      "screenshot_before": "step_000.png", "screenshot_after": "step_000.png"})
    traj = {"task": "x", "task_id": task_id or f"Booking--{task}", "start_url": urls[0],
            "model": "m", "max_steps": 15, "steps": steps, "terminated": True,
            "termination_reason": "agent_done", "final_answer": answer,
            "success_self_report": True, "judge_rubric": "", "verifier_path": ""}
    if with_traj:
        (d / 'trajectory.json').write_text(json.dumps(traj, indent=1))
    return d


def synth_after_db(task):
    """Copy the seed DB and apply the booking task's invited cart add."""
    dst = WORK / f"after_{task}.db"
    shutil.copy2(SEED_DB, dst)
    pid, ci, co = BOOKING_TASKS[task]
    con = sqlite3.connect(dst)
    con.execute(
        "INSERT INTO cart_item (id, user_id, property_id, check_in, check_out, adults,"
        " children, rooms, room_type, added_at) VALUES (991, 2, ?, ?, ?, 2, 0, 1,"
        " 'Standard Double Room', '2026-01-01 00:00:00')", (pid, ci, co))
    con.commit()
    con.close()
    return dst


def mutated_db(task):
    """Copy the seed DB and mutate an unrelated row (DB-write adversarial)."""
    dst = WORK / f"mut_{task}.db"
    shutil.copy2(SEED_DB, dst)
    con = sqlite3.connect(dst)
    if task in BOOKING_TASKS:
        con.execute("UPDATE property SET rating = 1.0 WHERE id = (SELECT MIN(id) FROM property)")
    else:
        con.execute("INSERT INTO user (email, password_hash, first_name, last_name)"
                    " VALUES ('x@y.z', 'h', 'X', 'Y')")
    con.commit()
    con.close()
    return dst


def run_verifier(task, run_dir, initial=None, after=None):
    cmd = [str(VENV_PY), str(VER / f'verify_{task}.py'), "--run_dir", str(run_dir),
           "--no_llm", "True"]
    if initial is not None:
        cmd += ["--initial_db", str(initial)]
    if after is not None:
        cmd += ["--after_db", str(after)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        v = json.loads(r.stdout)
    except Exception:
        v = {"pass": None, "reason": f"crash: {r.stderr[-300:]}"}
    return r.returncode, v


def expect(cond, label, sub):
    if not cond:
        raise AssertionError(f"[{label}] {sub}")


def run_negation_probes():
    """Acceptor probes D1/D2: a correct entity with the required fact DENIED
    must FAIL (count polarity + affirmative mention). Each probe is graded as a
    well-formed package with the task's real navigation and seed DBs."""
    for name, (n, paths, answer) in sorted(NEGATION_PROBES.items(), key=lambda kv: (kv[1][0], kv[0])):
        urls = [ORIGIN[:-1] + p for p in paths]
        d = build_run(n, urls, answer)
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"probe {name} T{n}",
               f"negation probe must FAIL, got rc={rc} v={v}")
        expect(v.get("reason") == PROBE_EXPECT_REASON[name], f"probe {name} T{n}",
               f"expected first-fail {PROBE_EXPECT_REASON[name]}, got {v.get('reason')}")
        print(f"OK  probe {name} T{n} FAIL ({PROBE_EXPECT_REASON[name]})")
    # affirmative guards: legitimate phrasings (idioms, other-clause negations)
    # must keep PASSing -- the guards may not over-block.
    for n, (paths, answer) in sorted(AFFIRMATIVE_GUARDS.items()):
        urls = [ORIGIN[:-1] + p for p in paths]
        d = build_run(n, urls, answer)
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 0 and v.get("pass") is True, f"guard T{n}",
               f"affirmative phrasing must PASS, got rc={rc} v={v}")
        print(f"OK  guard T{n} affirmative PASS")


def run_hardening_negatives():
    """Rework D9/D10: a booking run that also DELETES a seeded saved_property
    must FAIL the DB check, and a foreign-host navigation URL must not satisfy
    a nav check even when its path contains the required substrings."""
    # D9: invited cart add + an uninvited saved_property removal
    after = synth_after_db(6)
    con = sqlite3.connect(after)
    sp = con.execute("SELECT id FROM saved_property ORDER BY id LIMIT 1").fetchone()
    con.execute("DELETE FROM saved_property WHERE id=?", (sp[0],))
    con.commit(); con.close()
    urls, answer = P[6]
    d = build_run(6, urls, answer)
    rc, v = run_verifier(6, d, SEED_DB, after)
    expect(rc == 1 and v.get("pass") is False, "D9 T6",
           f"saved_property removal must FAIL, got rc={rc} v={v}")
    expect(v.get("reason") == "db_state", "D9 T6", f"expected db_state, got {v.get('reason')}")
    print("OK  D9 T6 saved_property-removal FAIL (db_state)")
    # D10: foreign-host URL with the right path must not count as navigation
    # (the run's start_url is the legitimate mirror origin; only the recorded
    # search step points at a foreign host whose path carries the substrings)
    urls, answer = P[30]
    foreign = [f"{ORIGIN}", f"https://foreign.example/search?q=London&breakfast=1&gym=1"]
    d = build_run(30, foreign, answer)
    rc, v = run_verifier(30, d, SEED_DB, SEED_DB)
    expect(rc == 1 and v.get("pass") is False, "D10 T30",
           f"foreign-host nav must FAIL, got rc={rc} v={v}")
    expect(v.get("reason") == "nav_london_bkf_gym_filters", "D10 T30",
           f"expected nav_london_bkf_gym_filters, got {v.get('reason')}")
    print("OK  D10 T30 foreign-host nav FAIL (nav_london_bkf_gym_filters)")


def main():
    from collections import defaultdict
    fails = defaultdict(list)

    for n in range(44):
        urls, answer = P[n]
        if n in BOOKING_TASKS:
            after = synth_after_db(n)
        else:
            after = SEED_DB

        # POSITIVE
        d = build_run(n, urls, answer)
        rc, v = run_verifier(n, d, SEED_DB, after)
        expect(rc == 0 and v.get("pass") is True, f"T{n}", f"positive failed: {v.get('reason')} {v.get('evidence')}")
        print(f"OK  T{n} positive")

        # NO-OP (homepage only, empty answer)
        d = build_run(n, [ORIGIN], "")
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"no-op not FAIL: {v}")
        expect(v.get("reason") == "final_answer_nonempty", f"T{n}", f"no-op reason={v.get('reason')}")
        print(f"OK  T{n} no-op FAIL (final_answer_nonempty)")

        # SHORTCUT (correct answer, homepage-only navigation)
        d = build_run(n, [ORIGIN], answer)
        rc, v = run_verifier(n, d, SEED_DB, after if n in BOOKING_TASKS else SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"shortcut not FAIL: {v.get('reason')}")
        print(f"OK  T{n} shortcut FAIL ({v.get('reason')})")

        # WRONG ANSWER (right navigation, wrong content)
        d = build_run(n, urls, WRONG[n])
        rc, v = run_verifier(n, d, SEED_DB, after if n in BOOKING_TASKS else SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"wrong-answer not FAIL: {v.get('reason')}")
        print(f"OK  T{n} wrong-answer FAIL ({v.get('reason')})")

        # FOREIGN TASK ID
        d = build_run(n, urls, answer, task_id=f"Booking--{(n + 1) % 44}")
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"foreign-id not FAIL: {v.get('reason')}")
        print(f"OK  T{n} foreign-task-id FAIL ({v.get('reason')})")

        # MISSING TRAJECTORY
        d = build_run(n, urls, answer, with_traj=False)
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"missing-traj not FAIL: {v.get('reason')}")
        print(f"OK  T{n} missing-trajectory FAIL ({v.get('reason')})")

        # MISSING SCREENSHOT
        d = build_run(n, urls, answer, shots=False)
        rc, v = run_verifier(n, d, SEED_DB, SEED_DB)
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"missing-shot not FAIL: {v.get('reason')}")
        print(f"OK  T{n} missing-screenshot FAIL ({v.get('reason')})")

        # DB WRITE
        d = build_run(n, urls, answer)
        rc, v = run_verifier(n, d, SEED_DB, mutated_db(n))
        expect(rc == 1 and v.get("pass") is False, f"T{n}", f"db-write not FAIL: {v.get('reason')}")
        expect("db_state" in str(v.get("reason")), f"T{n}", f"db-write reason={v.get('reason')}")
        print(f"OK  T{n} db-write FAIL ({v.get('reason')})")

    # ------------------------------------------------ tasks.jsonl contract
    rows = [json.loads(l) for l in (SITE / 'tasks.jsonl').read_text().splitlines() if l.strip()]
    assert len(rows) == 44, "tasks.jsonl must hold 44 rows"
    pristine = [json.loads(l) for l in (EVID / 'tasks.jsonl.before').read_text().splitlines() if l.strip()]
    for i, (r, p) in enumerate(zip(rows, pristine)):
        assert list(r.keys()) == ["web_name", "id", "ques", "web", "upstream_url", "verifier_path", "judge_rubric"], \
            f"row {i} key order/set: {list(r.keys())}"
        assert "answer" not in r
        assert all(r[k] == p[k] for k in ["web_name", "id", "ques", "web", "upstream_url"]), f"row {i} orig fields changed"
        assert r["verifier_path"] == f"sites/booking/verify/verify_{i}.py"
        assert (REPO / r["verifier_path"]).exists(), f"missing verifier {r['verifier_path']}"
        assert r["judge_rubric"].startswith("FACT CHECKPOINTS.") and len(r["judge_rubric"]) > 100, f"row {i} rubric"
    print("OK  tasks.jsonl contract: 44 rows, exact keys, no answer, verifiers exist, rubrics present, originals byte-identical")

    run_negation_probes()
    run_hardening_negatives()
    print("\nALL CONTRACT TESTS PASSED")


def test_clear_cdp_state_tool_fail_closed():
    """The runner's cookie-clear tool must fail closed when the CDP endpoint is
    unreachable (acceptor D4 contract: a silent success would let login state
    leak between tasks)."""
    r = subprocess.run([str(VENV_PY), str(VER / 'clear_cdp_state.py'),
                        "--cdp_url", "http://127.0.0.1:45999"], capture_output=True, text=True)
    assert r.returncode == 2, f"unreachable CDP must exit 2, got {r.returncode}: {r.stdout} {r.stderr}"


def test_clear_cdp_state_tool_source_contract():
    """The tool must be runner tooling, not part of the graded verifier suite:
    no graded verifier file may import it, and the tool imports playwright only
    lazily inside main (so the verifier suite stays stdlib-only)."""
    src = (VER / 'clear_cdp_state.py').read_text()
    assert 'import argparse' in src
    body = src.split('def main', 1)[1]
    assert 'from playwright.sync_api import sync_playwright' in body, "playwright import must be lazy (inside main)"
    for n in range(44):
        vsrc = (VER / f'verify_{n}.py').read_text()
        assert 'clear_cdp_state' not in vsrc, f"verify_{n}.py must not use the runner tool"
        assert 'playwright' not in vsrc, f"verify_{n}.py must stay stdlib-only"
    lib = (VER / 'verify_lib.py').read_text()
    assert 'playwright' not in lib and 'clear_cdp_state' not in lib


def test_grading_contract():
    """One pytest entry point running the full per-task matrix + contract checks."""
    main()


def test_negation_probes_and_hardening():
    """Pytest entry point for the acceptor-probe negatives (D1 count polarity,
    D2 affirmative mentions), the affirmative regression guards, and the D9/D10
    hardening negatives."""
    run_negation_probes()
    run_hardening_negatives()


if __name__ == "__main__":
    main()
