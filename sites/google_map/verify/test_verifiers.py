#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Google Map verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact trajectory shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's real-Chromium audit
of the running container), and the adversarial cases prove the verifiers
reject no-op runs, recall shortcuts, wrong answers, foreign task ids, broken
run packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because the
repository tracks no instance assets; set WH_CONTAINER to point at the site's
container when it is not the default wh-ver-google_map.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://localhost:41008"
TASKS = list(range(41))

# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/search?q=beauty+salons+in+seattle+washington&min_rating=4.8"],
        "Five beauty salons in Seattle, WA are rated above 4.8: Gene Juarez Salon & Spa "
        "(4.9), Habitude Salon & Day Spa (4.9), Sanctuary Salon & Med Spa (4.9), Urbane "
        "Hair Salon (4.9), and Vain Seattle (4.9). Le Salon Belleza is exactly 4.8 and "
        "does not exceed 4.8."),
    1: (["/search?q=bus+stops+in+altavista", "/place/altavista-va-main-st-amherst-st-bus-stop"],
        "The bus stop nearest to the Main St & Amherst St intersection in Altavista is "
        "Altavista Transit Stop #14, located at Main St & Amherst St, Altavista, VA 24501."),
    2: (["/search?q=apple+store+near+90028"],
        "Apple Stores close to zip 90028: Apple The Grove (2.6 mi), Apple Beverly Center "
        "(3.5 mi), Apple Americana at Brand (5.0 mi), Apple Century City (5.8 mi), Apple "
        "Sherman Oaks (7.7 mi), Apple Pasadena (9.5 mi), and Apple Third Street Promenade "
        "(11.6 mi)."),
    3: (["/directions?from=Central+Park+Zoo&to=Broadway+Theatre&mode=walking"],
        "The least-walking route from Central Park Zoo to the Broadway Theatre is via "
        "Main St: 0.7 miles, about 14 minutes walking (vs 15 min via Park Ave and "
        "18 min via Broadway)."),
    4: (["/directions?from=Boston+Logan+Airport&to=North+Station"],
        "Trip from Boston Logan International Airport to North Station: the fastest route "
        "is via I-93, 2.7 miles, about 7 minutes driving (alternatives: via I-90 Mass "
        "Pike 3.1 mi ~8 min, via US-1 3.6 mi ~10 min)."),
    5: (["/search?q=parking+near+thalia+hall+chicago", "/place/chicago-il-18th-street-parking"],
        "18th Street Parking (1801 S Racine Ave) is a parking lot near Thalia Hall in "
        "Chicago that isn't open 24 hours: it is open 7:00 AM to 11:00 PM daily."),
    6: (["/search?q=uniqlo"],
        "All Uniqlo locations in Chicago, IL: Uniqlo Michigan Avenue (830 N Michigan Ave), "
        "Uniqlo State Street (40 S State St), Uniqlo Lincoln Park (2526 N Clark St), and "
        "Uniqlo Wicker Park (1569 N Milwaukee Ave); Uniqlo Woodfield Mall (Schaumburg) and "
        "Uniqlo Oakbrook Center (Oak Brook) serve the wider Chicago area."),
    7: (["/search?q=bus+stops+in+alanson+mi"],
        "Bus stops in Alanson, MI: US-31 & Burr Ave Bus Stop, Main St & River St Bus Stop, "
        "Alanson Post Office Bus Stop, Alanson Village Hall Stop, and US-31 & Crooked Lake "
        "Stop."),
    8: (["/search?q=climbing+near+90028", "/place/los-angeles-ca-hollywood-boulders"],
        "A place to climb within 2 miles of zip 90028 is Hollywood Boulders (1107 N "
        "Bronson Ave), about 0.1 mi from the zip area."),
    9: (["/place/los-angeles-ca-los-angeles-hindu-temple?nearby_category=galleries"],
        "The art gallery nearest to Los Angeles Hindu Temple is Las Virgenes Canyon Fine "
        "Art (23501 Calabasas Rd, Calabasas, CA 91302), 0.4 mi from the temple - the "
        "closest of the six galleries nearby."),
    10: (["/place/castle-mountains-ca-castle-mountains-national-monument"],
         "Castle Mountains National Monument basic information: it is a United States "
         "national monument in eastern San Bernardino County, California, within the "
         "Mojave Desert, established in 2016; it protects grasslands, Joshua trees, and "
         "the historic Hart townsite. Located at Barnwell, CA 92364, open 24 hours; "
         "amenities include Hiking, Scenic views, Wildlife viewing, and No facilities."),
    11: (["/search?q=kids+maternity", "/place/ikea-renton"],
         "IKEA Renton (601 SW 41st St, Renton, WA) is a large store in Washington with a "
         "full kids' department, baby section, and maternity carried seasonally; it has "
         "ample free on-site parking (parking lot available)."),
    12: (["/search?q=burgers+near+44012&sort=rating"],
         "Five burger places near zip 44012, sorted by highest rating: 1) Avon Lake "
         "Burger Bar (4.8), 2) Pickle Bill's Lobster House (4.7), 3) Lake Erie Burger "
         "House (4.7), 4) Five Guys Avon Lake (4.6), 5) Bubba's 33 (4.5)."),
    13: (["/search?q=parking+in+gloucester",
          "/directions?from=Gloucester+Waterfront+Parking&to=North+Plymouth"],
         "I found Gloucester Waterfront Parking (1 Harbor Loop, Gloucester, MA 01930) and "
         "routed a ride from there to North Plymouth: the route is via I-93, 45.0 miles, "
         "about 54 minutes driving, with turn-by-turn map directions on the page."),
    14: (["/search?q=motorcycle+parking+near+radio+city+music+hall&sort=distance"],
         "Motorcycle parking near Radio City Music Hall: Icon Parking - Midtown 6th Ave "
         "(150 W 50th St, 0.1 mi), GMC Park Plaza Garage (124 W 47th St, 0.1 mi), and "
         "Rockefeller Plaza Motorcycle Parking Lot (30 Rockefeller Plaza, 0.1 mi) are "
         "the closest motorcycle parking facilities."),
    15: (["/search?q=parking+near+madison+square+garden&sort=distance",
          "/place/new-york-ny-chelsea-day-only-lot"],
         "The daytime-only parking nearest to Madison Square Garden is Chelsea Parking on "
         "30th (285 W 34th St, 0.1 mi), open Mon-Fri 7:00 AM to 6:00 PM and closed "
         "weekends. People say it is safe and clean, easy in and out with helpful staff, "
         "and pricey on event nights but very convenient - right next to MSG."),
    16: (["/search?q=ev+charging+parking+near+smithsonian&sort=distance",
          "/place/washington-dc-smithsonian-ev-charging-garage"],
         "The EV-charging-supported parking closest to the Smithsonian is Smithsonian "
         "Castle Garage (600 Maryland Ave SW, 0.2 mi), a multi-level garage beside the "
         "Smithsonian Castle with rapid EV charging stations on Level 2 (the Air & Space "
         "EV Parking Deck is also 0.2 mi away)."),
    17: (["/search?q=locksmiths+in+texas+city&hours=open_now"],
         "Locksmiths in Texas City open now but not open 24 hours: Texas City Locksmith "
         "Services (Mon-Sat 8 AM-8 PM), Mainland Locksmiths (Mon-Sun 9 AM-9 PM), and "
         "Gulf Coast Lock & Key (Mon-Sun 7 AM-10 PM). All Hours Locksmith Texas City and "
         "Texas Locks 24/7 are 24-hour and excluded."),
    18: (["/directions?from=Chicago&to=Los+Angeles"],
         "The route from Chicago to Los Angeles is 1,742 miles via I-80 W, about 1 d 5 h "
         "driving; the step-by-step route details include merging onto I-80 W heading "
         "away from Michigan and continuing for the long haul with a fuel/rest stop."),
    19: (["/search?q=Hilton+hotels+near+Pittsburgh+International+Airport",
          "/search?q=supermarket+near+DoubleTree+by+Hilton+Pittsburgh+Airport",
          "/directions?from=DoubleTree+by+Hilton+Pittsburgh+Airport&to=Giant+Eagle+Coraopolis&mode=walking"],
         "The Hilton hotel closest to Pittsburgh International Airport is DoubleTree by "
         "Hilton Pittsburgh Airport (8400 University Blvd, Coraopolis; 1.1 mi from the "
         "airport, closer than Hilton Garden Inn at 1.9 mi). The nearest supermarket is "
         "Giant Eagle Coraopolis (513 Thorn Run Rd); walking there takes about 49 minutes "
         "(2.5 miles via Main St)."),
    20: (["/place/washington-dc-national-air-and-space-museum?nearby_category=charging"],
         "The Tesla Destination Charger closest to the National Air and Space Museum is "
         "Tesla Destination Charger - CFA Plaza (525 8th St SE), 0.3 mi from the museum - "
         "closer than the L'Enfant Plaza (0.4 mi), The Wharf (0.7 mi), and Capital One "
         "Arena (0.8 mi) destination chargers."),
    21: (["/search?q=bus+stops+elm+street+oak+street+massachusetts",
          "/place/salem-ma-elm-st-oak-st-bus-stop"],
         "The nearest bus stop to the corner of Elm Street and Oak Street in "
         "Massachusetts is Elm St & Oak St Bus Stop in Salem, MA 01970 (a public bus "
         "stop at Elm St & Oak St)."),
    22: (["/search?q=best+buy+near+33139"],
         "The Best Buy store near zip code 33139 is Best Buy Miami Beach (1205 Washington "
         "Ave, Miami Beach, FL 33139), 0.2 mi from the zip area."),
    23: (["/directions?from=The+Metropolitan+Museum+of+Art&to=Times+Square&mode=walking"],
         "The shortest walking route from The Metropolitan Museum of Art to Times Square "
         "is via Main St: 1.8 miles, about 36 minutes walking (alternatives: 41 min via "
         "Park Ave, 47 min via Broadway)."),
    24: (["/directions?from=San+Francisco+International+Airport&to=Union+Square+San+Francisco&mode=driving"],
         "Driving from San Francisco International Airport to Union Square San "
         "Francisco: 11.6 miles, about 22 minutes via I-5 (alternatives: 13.0 mi ~24 min "
         "via US-101, 15.1 mi ~28 min via I-405)."),
    25: (["/search?q=parking+near+fox+theater+detroit", "/place/detroit-mi-fox-theatre-garage"],
         "A parking facility near the Fox Theatre in Detroit that closes at night is Fox "
         "Theatre Garage: it is open 7:00 AM to 12:00 AM (midnight), so it closes at "
         "night rather than staying open 24 hours."),
    26: (["/search?q=los+angeles"],
         "I searched Los Angeles on the map. The map area shows Los Angeles-area places "
         "including Santa Monica Pier, Getty Center, Griffith Observatory, Venice Beach, "
         "and the Hollywood Sign (42 results total across attractions, stores, "
         "restaurants, and more). The mirror offers no print/PDF control, so the map "
         "could not be printed as PDF."),
    27: (["/search?q=target+atlanta"],
         "Six Target stores are shown for Atlanta, GA: Target Atlantic Station, Target "
         "Midtown Atlanta, Target Edgewood, Target Lindbergh, Target Ponce City, and "
         "Target Cumberland - 6 results in total."),
    28: (["/settings"],
         "The Search Settings page offers: Distance units (Kilometers (km) / Miles (mi)); "
         "a Language selector (English, Espanol, Francais, Deutsch, Japanese, Chinese, "
         "Korean, Portuguese, Italiano, Arabic); a Default location input; Map type "
         "(Default, Satellite, Terrain); an Accessibility option to prefer "
         "wheelchair-accessible routes; and a Save settings button."),
    29: (["/search?q=bus+stops+in+ypsilanti+mi"],
         "Three bus stops in Ypsilanti, MI: Depot Town Bus Stop, Cross St & Washington St "
         "Bus Stop, and Michigan Ave & Hamilton St Bus Stop (others include Eastern "
         "Michigan University Bus Stop and the Ypsilanti Transit Center)."),
    30: (["/search?q=parking+near+brooklyn+bridge&hours=24h",
          "/place/brooklyn-ny-brooklyn-bridge-24h-parking"],
         "Brooklyn Bridge Waterfront Garage (55 Old Fulton St) is a parking lot near the "
         "Brooklyn Bridge that is open 24 hours. The user comments say it is very "
         "convenient for late-night visits to Brooklyn Bridge, clean and safe with "
         "friendly staff (a bit pricey but worth it), and the best parking option near "
         "the bridge that always has space."),
    31: (["/search?q=central+park+zoo", "/place/new-york-ny-central-park-zoo"],
         "The generated sharing link for Central Park Zoo is "
         "http://localhost:40008/place/new-york-ny-central-park-zoo (from the 'Share this "
         "place' box on the zoo's page)."),
    32: (["/search?q=plumbers+orlando&hours=open_now"],
         "Plumbers in Orlando available now but not open 24 hours: Orlando Plumbing "
         "Solutions (Mon-Sat 8 AM-8 PM), Central Florida Plumbers (Mon-Sun 7 AM-9 PM), "
         "and Mr. Rooter Plumbing Orlando (Mon-Sun 7 AM-10 PM). All Hours Plumbing "
         "Orlando and Roto-Rooter Orlando are 24-hour and excluded."),
    33: (["/place/denver-co-denver-international-airport"],
         "Denver International Airport's 12 visible reviews break down as 5-star: 4, "
         "4-star: 3, 3-star: 2, 2-star: 1, 1-star: 2 - the 2-star level has the least "
         "proportion (one review: 'Ticketing area is confusing for first-time flyers.'). "
         "Accessibility: Wheelchair accessible. Amenities: Parking, Free Wi-Fi, "
         "Restrooms, Shops, Restaurants, Train to city, Pet relief area."),
    34: (["/search?q=hiking+trail+near+80202"],
         "A hiking trail within 2 miles of zip 80202 is Cherry Creek Trail - about "
         "0.2 mi from the zip area (Commons Park Loop Trail and Highland Canal Trail are "
         "also within 2 miles)."),
    35: (["/place/big-bend-tx-big-bend-national-park"],
         "Big Bend National Park basic information: a United States national park in "
         "West Texas bordering Mexico, encompassing more than 801,000 acres of the "
         "Chihuahuan Desert along the Rio Grande. Open 24 hours at 1 Panther Junction; "
         "amenities include Camping, Hiking, River rafting, Visitor center, and "
         "Stargazing."),
    36: (["/search?q=pizza+near+30309&sort=rating"],
         "Five pizza restaurants near zip 30309 ranked by rating: 1) Antico Pizza "
         "Napoletana (4.8), 2) Varasano's Pizzeria (4.7), 3) Junior's Pizza Midtown "
         "(4.7), 4) Ammazza Midtown (4.6), 5) Tony's Family Pizzeria (4.6)."),
    37: (["/search?q=parking+in+salem+ma",
          "/directions?from=Salem+Waterfront+Parking&to=Marblehead"],
         "I located Salem Waterfront Parking (10 Blaney St, Salem, MA 01970) and routed "
         "from there to Marblehead: 2.3 miles, about 6 minutes driving via I-93, with "
         "the route and turn-by-turn map directions displayed."),
    38: (["/search?q=bicycle+parking+near+empire+state+building&sort=distance"],
         "Bicycle parking near the Empire State Building: 34th Street DOT Bike Corral "
         "(0.1 mi) and Koreatown Bike Parking Corral (0.1 mi) are the closest, with "
         "Herald Square Bike Parking Rack (0.2 mi) also nearby."),
    39: (["/directions?from=Miami&to=New+Orleans"],
         "The route from Miami to New Orleans is 669 miles via I-95, about 11 h 9 min "
         "driving; the detailed route steps include merging onto I-95 heading away from "
         "Florida, continuing for the long haul, a fuel/rest stop, and approaching "
         "Louisiana."),
    40: (["/search?q=lobster+restaurant+boston&min_rating=4.6",
          "/place/boston-ma-yvonne-s-boston-lobster"],
         "Yvonne's Boston Lobster (4.6 stars, 80 Atlantic Ave) is a Boston restaurant "
         "serving Boston lobster with a rating of 4.6 or higher. Its one-star review says "
         "the lobster was overcooked and rubbery, the service was slow, it was way "
         "overpriced, and the reviewer would not recommend it."),
}

# Per-task content adversarial: a plausible-but-wrong answer after the required
# navigation (must FAIL every verifier).
WRONG_ANSWER = {
    0: "Five beauty salons in Seattle rated above 4.8: Le Salon Belleza, Belltown "
       "Beauty Bar, Evergreen Beauty Bar, Ballard Beauty Salon, and Parkwood Beauty Salon.",
    1: "The nearest bus stop is Bedford Ave Bus Stop (Bedford Ave, Altavista, VA).",
    2: "The closest Apple Store to 90028 is the Melrose Concept Store on Rodeo Drive.",
    3: "The least-walking route is via Broadway: 0.9 miles, about 18 minutes.",
    4: "The trip takes 3.6 miles via US-1, about 10 minutes.",
    5: "Blue Island Avenue Garage is a parking garage near Thalia Hall open 24 hours.",
    6: "The only Uniqlo in Chicago is Uniqlo Michigan Avenue.",
    7: "The bus stops in Alanson are Depot Town Bus Stop and Cross St & Washington St Bus Stop.",
    8: "Cliffs of Id - LA Climbing (2537 S Fairfax Ave, Culver City) is a place to climb "
       "within 2 miles of 90028 - 6.9 mi away.",
    9: "The nearest art gallery to Los Angeles Hindu Temple is Malibu Creek Art Gallery (1.6 mi).",
    10: "Castle Mountains is a national monument established in 1910 in the Sonoran Desert.",
    11: "Bellevue Baby & Kids (10250 NE 8th St, Bellevue) is a large store with kids' "
        "essentials; it has a parking lot available.",
    12: "Top five burgers near 44012 by rating: 1) Burger King - Avon Lake (4.1), "
        "2) Classic Burger Co. (3.8), 3) Pier 22 Burger Bar (4.0), 4) Wendy's Avon Lake "
        "(4.2), 5) Red Robin Avon Lake (4.3).",
    13: "I found Fenway Park parking and routed to North Plymouth: 12 miles, 20 minutes via I-90.",
    14: "Herald Square Bike Parking Rack (1330 Broadway) is parking near Radio City Music Hall.",
    15: "The nearest daytime parking to MSG is Penn Station South Lot (245 W 34th St). "
        "There are no reviews yet.",
    16: "The closest EV parking to the Smithsonian is Jefferson Memorial EV Parking Lot "
        "(16 E Basin Dr SW).",
    17: "All Hours Locksmith Texas City (1400 Palmer Hwy) is a locksmith open now in Texas City.",
    18: "The route from Chicago to Los Angeles is 2,800 km via Route 66, about 26 hours.",
    19: "The closest Hilton to Pittsburgh Airport is Hilton Pittsburgh Airport (8300 "
        "University Blvd), and the nearest supermarket Giant Eagle Moon Township is an "
        "8-minute walk away.",
    20: "The closest Tesla Destination Charger is at L'Enfant Plaza (480 L'Enfant Plaza SW).",
    21: "The nearest bus stop to Elm & Oak is Elm St & Main St Bus Stop in Cambridge, MA.",
    22: "Best Buy Dadeland (8655 N Kendall Dr) is the Best Buy near 33139.",
    23: "The shortest walking route is via Broadway: 2.4 miles, 47 minutes.",
    24: "Driving from SFO to Union Square takes 13.0 miles via US-101, 24 minutes.",
    25: "Foxtown Garage is parking near the Fox Theatre open 24 hours.",
    26: "The Los Angeles map could not be printed as PDF.",
    27: "Seven Target stores are shown in Atlanta: Atlantic Station, Midtown, Edgewood, "
        "Lindbergh, Ponce City, Cumberland, and Lenox Square.",
    28: "The settings page has a Save settings button and a back link.",
    29: "The Ypsilanti bus stops are Walker Rd @ Moore Rd Stop and Lake Rd @ Walker Rd Stop.",
    30: "Jay Street Garage (322 Jay St) is open 24 hours near the Brooklyn Bridge; "
        "there are no user comments yet.",
    31: "The sharing link is https://maps.google.com/?q=Central+Park+Zoo.",
    32: "Roto-Rooter Orlando is a plumber in Orlando open now.",
    33: "The 1-star level has the least proportion of reviews at Denver International Airport.",
    34: "Red Rocks Trail is a hiking trail within 2 miles of 80202 (9.6 mi away).",
    35: "Big Bend is a national park in East Texas near the Gulf of Mexico.",
    36: "Five pizza places near 30309: 1) Pizza Hut Midtown Atlanta (3.8), 2) Grant "
        "Central Pizza (4.3), 3) Double Zero Atlanta (4.4), 4) Midtown Pizza Kitchen "
        "(4.5), 5) Fellini's Pizza Atlanta (4.5).",
    37: "I found parking in Salem and routed to Marblehead: 10 miles in 15 minutes via I-95.",
    38: "Bryant Park Motorcycle Parking Corral is bicycle parking near the Empire State Building.",
    39: "The route from Miami to New Orleans is 1,320 km via I-10, about 12 hours 30 minutes.",
    40: "Yvonne's Boston Lobster (4.6) has a one-star review that says the lobster was amazing.",
}

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8


def make_run(root: Path, task: int, paths, answer, *, task_id=None, origin=ORIGIN,
             drop_trajectory=False, break_screenshot=False):
    run = root / f"run_{task}"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    paths = list(paths)
    steps = []
    for index, path in enumerate(paths):
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        steps.append({"step": index, "url": origin + path, "action": "click",
                      "action_result": {"success": True}, "screenshot_after": shot})
    final_shot = f"step_{len(paths):03d}.png"
    if not break_screenshot:
        (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(paths), "url": origin + (paths[-1] if paths else "/"),
                  "action": "done", "action_result": {"success": True},
                  "screenshot_after": final_shot})
    trajectory = {
        "task_id": task_id or f"Google Map--{task}",
        "task": "fixture",
        "start_url": origin + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "steps": steps,
    }
    if not drop_trajectory:
        (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def run_verifier(task: int, run_dir: Path, initial_db: Path, after_db: Path):
    script = VERIFY_DIR / f"verify_{task}.py"
    r = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial_db), "--after_db", str(after_db),
         "--container", "unused-container", "--no_llm", "True"],
        capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    verdict["returncode"] = r.returncode
    return verdict


SEED_DB = None


def seed_db(tmp: Path) -> Path:
    global SEED_DB
    if SEED_DB is None:
        SEED_DB = verify_lib.fetch_db(
            __import__("os").environ.get("WH_CONTAINER", "wh-ver-google_map"), "instance_seed")
    db = tmp / "seed_copy.db"
    shutil.copy2(SEED_DB, db)
    return db


class VerifierTests(unittest.TestCase):
    def execute(self, task, *, answer=None, paths=None, task_id=None,
                drop_trajectory=False, break_screenshot=False, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            good_paths, good_answer = POSITIVE[task]
            run = make_run(root, task,
                           paths if paths is not None else good_paths,
                           answer if answer is not None else good_answer,
                           task_id=task_id, drop_trajectory=drop_trajectory,
                           break_screenshot=break_screenshot)
            return run_verifier(task, run, initial, after)

    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task)
                self.assertTrue(result["pass"], f"task {task}: {result}")

    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"], answer="")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)

    def test_shortcut_correct_answer_without_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"])
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, answer=WRONG_ANSWER[task])
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_foreign_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, task_id="Google Map--999")
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_missing_trajectory_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, drop_trajectory=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_missing_screenshot_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, break_screenshot=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_database_write_fails_read_only_check(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task,
                    mutate=lambda db: db.execute("UPDATE place SET rating = rating + 0.1 WHERE id = 1"))
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "db_state")

    def test_task0_le_salon_belleza_substitution_fails(self):
        # a list that substitutes the exactly-4.8 Le Salon Belleza for one of the
        # five 4.9 salons must FAIL
        answer = ("Five beauty salons above 4.8 in Seattle: Gene Juarez Salon & Spa, "
                  "Habitude Salon & Day Spa, Sanctuary Salon & Med Spa, Urbane Hair "
                  "Salon, and Le Salon Belleza.")
        result = self.execute(0, answer=answer)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_names_all_five_qualifying")

    def test_task13_municipal_lot_origin_passes(self):
        # the second valid Gloucester parking origin yields the same primary route
        paths = ["/search?q=parking+in+gloucester",
                 "/directions?from=Main+St+Municipal+Lot+Gloucester&to=North+Plymouth"]
        answer = ("Main St Municipal Lot Gloucester (169 Main St) is a parking lot in "
                  "Gloucester; the route from there to North Plymouth is via I-93, "
                  "45.0 miles, about 54 minutes driving with map directions shown.")
        result = self.execute(13, paths=paths, answer=answer)
        self.assertTrue(result["pass"], result)

    def test_task16_air_space_deck_tie_passes(self):
        # the tied 0.2 mi Air & Space EV Parking Deck is also accepted
        answer = ("The closest EV-charging-supported parking to the Smithsonian is the "
                  "Air & Space EV Parking Deck (650 Independence Ave SW, 0.2 mi), which "
                  "has on-site EV charging stations.")
        result = self.execute(16, answer=answer)
        self.assertTrue(result["pass"], result)

    def test_task27_nine_results_reading_passes(self):
        # the verbatim 'Target stores in Atlanta, GA' search lists 9 places
        # (6 Target + 3 distractors); both count readings are accepted while the
        # store names pin the Target stores
        answer = ("The Target search in Atlanta, GA shows 9 results, six of which are "
                  "Target stores: Target Atlantic Station, Target Midtown Atlanta, "
                  "Target Edgewood, Target Lindbergh, Target Ponce City, and Target "
                  "Cumberland; Whole Foods Market Midtown, Margaret Mitchell House, and "
                  "REI Co-op Atlanta are the other three results.")
        result = self.execute(27, answer=answer)
        self.assertTrue(result["pass"], result)

    def test_task12_unsorted_rating_order_fails(self):
        answer = ("Five burger places near 44012: 1) Bubba's 33 (4.5), 2) Five Guys "
                  "Avon Lake (4.6), 3) Lake Erie Burger House (4.7), 4) Pickle Bill's "
                  "Lobster House (4.7), 5) Avon Lake Burger Bar (4.8).")
        result = self.execute(12, answer=answer)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_sorted_by_rating_desc")

    def test_task36_unsorted_rating_order_fails(self):
        answer = ("Five pizza places near 30309: 1) Junior's Pizza Midtown (4.7), "
                  "2) Antico Pizza Napoletana (4.8), 3) Ammazza Midtown (4.6), "
                  "4) Tony's Family Pizzeria (4.6), 5) Varasano's Pizzeria (4.7).")
        result = self.execute(36, answer=answer)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_ranked_by_rating_desc")


class ContractTests(unittest.TestCase):
    def test_task_file_carries_verifier_and_rubric_for_every_task(self):
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 41)
        self.assertEqual([row["id"] for row in rows], [f"Google Map--{i}" for i in TASKS])
        for row in rows:
            self.assertEqual(
                sorted(row.keys()),
                sorted(["web_name", "id", "ques", "web", "upstream_url",
                        "verifier_path", "judge_rubric"]), row["id"])
            self.assertEqual(row["verifier_path"],
                             f"sites/google_map/verify/verify_{row['id'].split('--')[1]}.py")
            self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."), row["id"])
            self.assertNotIn("answer", row)
            repo_file = SITE_DIR.parent.parent / row["verifier_path"]
            self.assertTrue(repo_file.is_file(), row["verifier_path"])

    def test_verifier_scripts_exist_and_are_deterministic(self):
        for task in TASKS:
            script = VERIFY_DIR / f"verify_{task}.py"
            self.assertTrue(script.is_file(), script)
            source = script.read_text()
            self.assertNotIn("urllib.request", source)          # no LLM/network calls
            self.assertNotIn("requests.post", source)
            self.assertIn(f"'Google Map--{task}'", source)

    def test_verify_lib_run_package_gate_rejects_broken_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            run = make_run(root, 0, *POSITIVE[0])
            verdict = run_verifier(0, run, initial, initial)
            self.assertTrue(verdict["pass"], verdict)
            (run / "trajectory.json").unlink()
            verdict = run_verifier(0, run, initial, initial)
            self.assertFalse(verdict["pass"], verdict)
            self.assertEqual(verdict.get("reason"), "run_package_valid")


if __name__ == "__main__":
    unittest.main()
