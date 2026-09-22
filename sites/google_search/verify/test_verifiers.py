#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Google Search verifier.

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
container when it is not the default wh-ver-google_search.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://localhost:41009"
TASKS = list(range(43))

# task -> (search query, answer-page path, model answer). The navigation paths
# and answers mirror the reviewer's recorded audit of the served pages.
POSITIVE = {
    0: ("Guardians of the Galaxy Vol. 3 initial release date",
        "www.imdb.com/title/tt6791350/",
        "Guardians of the Galaxy Vol. 3 was initially released in the United States on May 5, 2023 (directed by James Gunn)."),
    1: ("Kevin Durant bio",
        "www.basketball-reference.com/players/d/duranke01.html",
        "Kevin Wayne Durant (born September 29, 1988) is an American professional basketball player for the Phoenix Suns of the NBA."),
    2: ("Los Angeles Lakers latest news",
        "www.lakers.com/news",
        "The latest Lakers news headline is: Lakers hold off Wolves in fourth-quarter rally at Crypto.com Arena (124-110 win over the Wolves)."),
    3: ("top comedy movies sorted by user ratings top 5",
        "www.imdb.com/chart/top-comedies/",
        "Top 5 comedy movies by user rating: 1. Forrest Gump (8.8), 2. Life Is Beautiful (8.6), 3. Back to the Future (8.5), 4. The Intouchables (8.5), 5. Modern Times (8.5)."),
    4: ("most played games in Steam current players",
        "store.steampowered.com/charts/mostplayed",
        "The most played game on Steam is Counter-Strike 2, with 938,210 players in game at this time."),
    5: ("Phoenix Suns latest NBA game score",
        "www.espn.com/nba/team/schedule/_/name/phx/phoenix-suns",
        "The Phoenix Suns' latest game was a 124-110 win over the Minnesota Timberwolves."),
    6: ("monthly trending searches Columbus Ohio",
        "trends.google.com/trends/explore?geo=US-OH&q=columbus",
        "Monthly trending searches in Columbus: local sports team (100), weekend events (82), school district news (64), and downtown construction (48)."),
    7: ("AirDrop continue transmitting over web out of range software requirements",
        "support.apple.com/guide/iphone/use-airdrop-iphcd2f071e2/ios",
        "AirDrop can continue transfers over the internet when out of range; it requires iOS 17.1 or later on both devices, both signed in to iCloud with an active data connection."),
    8: ("Oscars 2023 Must-See Moments first comment",
        "www.youtube.com/watch?v=oscars2023moments",
        "The first comment under the video belongs to @AwardsArchive; it has 1.2K thumbs up and 87 replies."),
    9: ("Prometheus movie IMDb Rotten Tomatoes rating",
        "www.rottentomatoes.com/m/prometheus_2012",
        "Prometheus (2012) is rated 7.0/10 on IMDb and 73% on the Rotten Tomatoes Tomatometer."),
    10: ("Billboard number 1 artist weekly chart top 10 songs",
         "www.billboard.com/charts/artist-100/",
         "The Billboard Artist 100's number one artist this week is Kendrick Lamar; his song 'luther' (with SZA) tops the Hot 100 and his album 'GNX' tops the Billboard 200."),
    11: ("FlightAware busiest airport last week total arrivals departures",
         "www.flightaware.com/live/airport_status_bigmap.rvt",
         "According to FlightAware, the busiest airport last week was Hartsfield-Jackson Atlanta (ATL) with 11,650 total arrivals and departures (5,820 arrivals and 5,830 departures)."),
    12: ("Tom Brady most touchdowns single season year",
         "www.nfl.com/news/tom-brady-records",
         "Tom Brady had his most touchdowns in a single season in 2007, throwing 50 touchdown passes for the New England Patriots."),
    13: ("Jerry Trainor upcoming projects",
         "www.imdb.com/name/nm1601989/",
         "Jerry Trainor's upcoming projects: The Last Goodbye (producer, announced) and iCarly: One Night Only (Spencer Shay, pre-production)."),
    14: ("retired player James Smith 2020-2021 club",
         "www.transfermarkt.com/james-smith/profil/spieler/jamessmith",
         "James Smith was a member of Mansfield Town during the 2020-2021 season (Fourth tier, 38 appearances, 2 goals)."),
    15: ("twitter login webagenttest@testmail.com",
         "x.com/login",
         "The login was not successful. The X login page asks for phone, email, or username and a password, but the attempt with the provided credentials could not be completed."),
    16: ("OpenAI community Reddit members hottest news",
         "www.reddit.com/r/OpenAI/",
         "The r/OpenAI community has 2.4M members; the hottest post right now is 'Discussion thread — weekly highlights from r/OpenAI' (3.2k upvotes, 412 comments)."),
    17: ("Donald Trump children names kids",
         "www.whitehouse.gov/45/the-trump-family/",
         "Donald Trump's five children are Donald Trump Jr., Ivanka Trump, Eric Trump, Tiffany Trump, and Barron Trump."),
    18: ("most recent FIFA World Cup winner where when held",
         "www.fifa.com/tournaments/mens/worldcup/recent",
         "The most recent World Cup was held in Qatar in 2022, and Argentina won it, defeating France in the final."),
    19: ("Bert GitHub latest commit SHA first 7 bits changed",
         "github.com/google-research/bert/commits/master",
         "The first 7 bits of the SHA of BERT's latest commit are eedf571; the commit updated tokenization for unicode normalization edge cases."),
    20: ("latest Fast and Furious movie release date",
         "www.themoviedb.org/movie/385687-fast-x",
         "The latest Fast & Furious movie is Fast X, released on May 19, 2023."),
    21: ("top 5 highest grossing animated movies box office",
         "www.boxofficemojo.com/genre/sg2962499329/",
         "Top 5 highest-grossing animated movies by worldwide box office: 1. Inside Out 2 ($1,698,800,000), 2. Frozen II ($1,453,683,476), 3. The Super Mario Bros. Movie ($1,361,972,232), 4. Frozen ($1,290,000,000), 5. Incredibles 2 ($1,242,805,359)."),
    22: ("top 3 trending topics this month New York City",
         "trends.google.com/trends/explore?geo=US-NY",
         "The top three trending topics in New York City this month: local sports team, weekend events, and school district news."),
    23: ("LeBron James short biography",
         "www.biography.com/athletes/lebron-james",
         "LeBron Raymone James (born December 30, 1984, in Akron, Ohio) is an American professional basketball player for the Los Angeles Lakers, drafted first overall in 2003."),
    24: ("closest star system to Solar System discovered planets",
         "www.space.com/nearby-star-systems",
         "The closest star system to the Solar System is Alpha Centauri, a triple system whose faint red dwarf member has a confirmed Earth-mass planet orbiting it."),
    25: ("Manchester United latest news headline Premier League",
         "www.manutd.com/en/news",
         "The latest Manchester United headline: 'United secure crucial three points at Old Trafford' (match report, 2 hours ago)."),
    26: ("Adobe Photoshop Mac hardware requirements latest version",
         "helpx.adobe.com/photoshop/system-requirements.html",
         "Adobe Photoshop on Mac requires an Apple silicon (M1) or Intel multicore processor, macOS 12.0 (Monterey) or later, 8 GB of RAM (16 GB recommended), a Metal-capable GPU, and 20 GB of disk space."),
    27: ("Paris current air quality index AQI",
         "www.iqair.com/world-air-quality-ranking/paris",
         "Paris's current air quality index is 78 (US AQI, Moderate), with PM2.5 as the main pollutant."),
    28: ("Inception movie IMDb Metacritic score",
         "www.metacritic.com/movie/inception/",
         "Inception (2010) scores 8.8/10 on IMDb and 74/100 on Metacritic (Metascore)."),
    29: ("men's 100m sprint world record current",
         "worldathletics.org/records/by-category/world-records",
         "The current world record for the men's 100m sprint is 9.58 seconds, set in 2009 in Berlin."),
    30: ("Spotify Global Top 50 number one artist top 10 songs",
         "open.spotify.com/playlist/37i9dQZEVXbMDoHDwVN2tF",
         "The current number-one artist on Spotify's Global Top 50 is Bad Bunny, with 'DtMF' at #1 and 'BAILE INoLVIDABLE' at #2."),
    31: ("Cristiano Ronaldo most goals single season year",
         "www.espn.com/soccer/player/_/id/13/cristiano-ronaldo",
         "Cristiano Ronaldo scored his most goals in a single season in 2014-15, with 61 goals in all competitions for Real Madrid."),
    32: ("most recent UEFA Champions League final location date winner",
         "www.uefa.com/uefachampionsleague/history/finals/",
         "The most recent UEFA Champions League final was held at Wembley, London in 2024; Real Madrid won it 2-0 over Borussia Dortmund."),
    33: ("TensorFlow GitHub repository latest commit SHA",
         "github.com/tensorflow/tensorflow/commits/master",
         "The SHA of the latest commit in the TensorFlow repository is a1b2c3d ('chore: bump linter'); I pasted the SHA into a search textbox on the site."),
    34: ("distance from Earth to Mars today",
         "www.space.com/mars-distance-from-earth-today.html",
         "As of today, Mars sits roughly 217 million kilometers from Earth, about twelve light-minutes."),
    35: ("latest research paper black holes Nature Astronomy",
         "www.nature.com/natastron/",
         "The latest black-holes paper in Nature Astronomy is by A. M. Pereira et al. (volume 8, pages 412-426), reporting a census of intermediate-mass black-hole candidates and accretion physics around supermassive black holes."),
    36: ("most recent Nobel Prize Physics winner contribution",
         "www.nobelprize.org/prizes/physics/",
         "The most recent Nobel Prize in Physics (2025) was awarded to John Clarke, Michel H. Devoret, and John M. Martinis for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit."),
    37: ("top 3 super-earth planets brief introduction",
         "exoplanets.nasa.gov/what-is-an-exoplanet/types-of-planets/super-earth/",
         "Top super-Earth planets: Kepler-452b (a habitable-zone super-Earth around a Sun-like star), LHS 1140 b (a rocky habitable-zone super-Earth 40 light-years away), and TOI-715 b (a recently confirmed super-Earth in the conservative habitable zone)."),
    38: ("next visible solar eclipse North America date one after",
         "eclipse.gsfc.nasa.gov/SEdecade/SEdecade2041.html",
         "The next total solar eclipse visible from North America is on August 23, 2044 (path through Montana and North Dakota); the one after that is on August 12, 2045."),
    39: ("top 10 trending travel destinations 2024 blog Asia",
         "www.travelandleisure.com/trip-ideas/best-places-to-go",
         "The 2024 trending-destinations blog leads with an emerging Asian capital, and Asia features prominently — the coverage highlights Japan, Vietnam and Indonesia; of the blog's trending destinations for 2024, the Asian ones include that emerging Asian capital."),
    40: ("Mount Kilimanjaro elevation",
         "www.britannica.com/place/Mount-Kilimanjaro",
         "Mount Kilimanjaro stands 5,895 meters (19,341 feet) above sea level, the highest mountain in Africa."),
    41: ("Los Angeles current air pollution level statistics",
         "www.airnow.gov/",
         "Los Angeles's current air quality index is 105, Unhealthy for Sensitive Groups, with PM2.5 the dominant pollutant."),
    42: ("American English British English major differences article",
         "www.babbel.com/en/magazine/british-vs-american-english",
         "The article explains the major differences between American and British English: spelling (colour vs color, centre vs center, organise vs organize, defence vs defense), vocabulary differences, and pronunciation (rhoticity)."),
}

# Per-task content adversarial: a plausible-but-wrong answer after the required
# navigation (must FAIL every verifier).
WRONG_ANSWER = {
    0: "Guardians of the Galaxy Vol. 3 was initially released on April 27, 2023.",
    1: "Kevin Durant (born September 13, 1988) currently plays for the Oklahoma City Thunder.",
    2: "The latest Lakers news headline is 'LeBron James announces retirement from basketball'.",
    3: "Top 5 comedy movies by rating: 1. Superbad (8.1), 2. Anchorman (8.0), 3. Groundhog Day (8.0), 4. Dumb and Dumber (7.8), 5. Step Brothers (7.6).",
    4: "The most played game on Steam is Dota 2, with 658,434 current players.",
    5: "The Suns' latest game was a 102-98 loss to the Boston Celtics.",
    6: "Trending searches in Columbus this month: Broadway shows, subway updates, and Knicks games.",
    7: "AirDrop over the web requires iOS 16.4 or later.",
    8: "The first comment is by @MovieFan_HQ, with 500 thumbs up and 10 replies.",
    9: "Prometheus is rated 6.5/10 on IMDb and 48% on Rotten Tomatoes.",
    10: "The Billboard number-one artist is Taylor Swift with 'Cruel Summer'.",
    11: "The busiest airport last week was Dallas/Fort Worth with 9,810 total operations.",
    12: "Tom Brady threw his most touchdowns (40) in the 2021 season.",
    13: "Jerry Trainor's upcoming project is a new Marvel superhero movie.",
    14: "James Smith played for Crawley Town in the 2020-2021 season.",
    15: "The login was successful and I am now signed in to the Twitter account.",
    16: "r/OpenAI has 1.2 million members and the hottest post is about GPT-5 rumors.",
    17: "Trump's kids are Michael, Sarah, John, Emily, and Robert.",
    18: "The most recent World Cup was held in Russia in 2018, and France won it.",
    19: "BERT's latest commit SHA starts with 8c50416 and it fixed a GPU memory error.",
    20: "The latest Fast & Furious movie is F9, released on June 25, 2021.",
    21: "Top 5 animated movies: 1. Frozen II, 2. Inside Out 2, 3. Minions, 4. Toy Story 4, 5. Finding Dory.",
    22: "NYC's top three trending topics: Broadway shows, pizza, and subway delays.",
    23: "LeBron James was born on December 30, 1985, in Cleveland, Ohio.",
    24: "The closest star system is Barnard's Star, with no discovered planets.",
    25: "The latest Manchester United headline is 'Solskjaer sacked as United manager'.",
    26: "Photoshop on a Mac requires Windows 11, 4 GB of RAM, and any GPU.",
    27: "Paris's current air quality index is 45 (Good).",
    28: "Inception scores 9.0 on IMDb and 89 on Metacritic.",
    29: "The men's 100m world record is 9.69 seconds, set in 2008 in Beijing.",
    30: "The Spotify Global Top 50 number-one artist is Taylor Swift with 'Cruel Summer'.",
    31: "Ronaldo scored his most goals (48) in the 2019-20 season with Juventus.",
    32: "The most recent Champions League final was held in Istanbul in 2023; Manchester City won 1-0.",
    33: "The SHA of the latest TensorFlow commit is f4e5d6c.",
    34: "Mars is 99 million kilometers from Earth today.",
    35: "The latest Nature Astronomy black-holes paper is the neutron-star discovery by Smith et al.",
    36: "The most recent Physics Nobel (2023) went to Agostini, Krausz and L'Huillier for attosecond light pulses.",
    37: "The top super-Earths are Mars, Venus, and Mercury.",
    38: "The next solar eclipse visible from North America is on April 8, 2024, and the one after that on April 30, 2041.",
    39: "None of the top-10 trending destinations for 2024 are in Asia; the list is all-European, led by Lisbon.",
    40: "Mount Kilimanjaro's elevation is 4,900 meters.",
    41: "Los Angeles's current air quality index is 42 (Good).",
    42: "American and British English differ mainly in accent; there are no systematic spelling differences.",
}

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8


def make_run(root: Path, task: int, paths, answer, *, task_id=None, origin=ORIGIN,
             drop_trajectory=False, break_screenshot=False, extra_steps=()):
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
    for extra in extra_steps:
        index = len(steps)
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        step = {"step": index, "url": origin + "/", "action": extra.get("action", "click"),
                "action_result": {"success": True}, "screenshot_after": shot}
        if "params" in extra:
            step["params"] = extra["params"]
        steps.append(step)
    final_shot = f"step_{len(steps):03d}.png"
    if not break_screenshot:
        (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(steps), "url": origin + (paths[-1] if paths else "/"),
                  "action": "done", "action_result": {"success": True},
                  "screenshot_after": final_shot})
    trajectory = {
        "task_id": task_id or f"Google Search--{task}",
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


def positive_paths(task: int):
    query, page, _answer = POSITIVE[task]
    search = "/search?q=" + urllib.parse.quote_plus(query)
    return [search, "/external/" + page]


def positive_extra_steps(task: int):
    if task == 33:
        # task 33 additionally requires the SHA pasted into a site textbox
        return ({"action": "input", "params": {"index": 2, "text": "a1b2c3d"}},)
    return ()


WT_ROOT = SITE_DIR.parents[1]
# The verifier CLI runs under agent_demo's uv project (exactly the way
# agent_demo/eval_judge.py invokes it: `uv run python <verifier>` from
# agent_demo/, whose venv provides simpleArgParser).
AGENT_DEMO_PY = WT_ROOT / "agent_demo" / ".venv" / "bin" / "python"


def run_verifier(task: int, run_dir: Path, initial_db: Path, after_db: Path):
    script = VERIFY_DIR / f"verify_{task}.py"
    py = str(AGENT_DEMO_PY) if AGENT_DEMO_PY.exists() else sys.executable
    r = subprocess.run(
        [py, str(script), "--run_dir", str(run_dir),
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


def seed_db(tmp: Path, name: str = "seed_copy.db") -> Path:
    global SEED_DB
    if SEED_DB is None:
        SEED_DB = verify_lib.fetch_db(
            os.environ.get("WH_CONTAINER", "wh-ver-google_search"), "instance_seed")
    db = tmp / name
    shutil.copy2(SEED_DB, db)
    return db


class VerifierTests(unittest.TestCase):
    maxDiff = None

    def execute(self, task, *, answer=None, paths=None, task_id=None,
                drop_trajectory=False, break_screenshot=False, dirty_db=False,
                use_search_nav=True, extra_steps=None):
        """Run verify_<task> against a synthetic run; returns the verdict."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            initial = seed_db(tmp, "initial.db")
            after = seed_db(tmp, "after.db")
            if dirty_db:
                con = sqlite3.connect(after)
                con.execute("UPDATE topic SET name = name || ' (tampered)' WHERE id = (SELECT MIN(id) FROM topic)")
                con.commit()
                con.close()
            if paths is None:
                paths = positive_paths(task) if use_search_nav else ["/"]
            run = make_run(tmp, task, paths, answer if answer is not None else POSITIVE[task][2],
                           task_id=task_id, drop_trajectory=drop_trajectory,
                           break_screenshot=break_screenshot,
                           extra_steps=extra_steps if extra_steps is not None else positive_extra_steps(task))
            return run_verifier(task, run, initial, after)

    # ------------------------------------------------------------ positives
    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                verdict = self.execute(task)
                self.assertTrue(verdict["pass"], f"task {task}: {verdict}")
                self.assertEqual(verdict["returncode"], 0)

    # ------------------------------------------------------------ adversarials
    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                verdict = self.execute(task, paths=["/"], answer="")
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "final_answer_nonempty")
                self.assertEqual(verdict["returncode"], 1)

    def test_shortcut_correct_answer_without_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                verdict = self.execute(task, paths=["/"])
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "nav_task_search")
                self.assertEqual(verdict["returncode"], 1)

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                verdict = self.execute(task, answer=WRONG_ANSWER[task])
                self.assertFalse(verdict["pass"], f"task {task}: {verdict}")
                self.assertNotEqual(verdict["reason"], "nav_task_search")
                self.assertEqual(verdict["returncode"], 1)

    def test_foreign_task_replay_fails(self):
        for task in (0, 21, 42):
            with self.subTest(task=task):
                verdict = self.execute(task, task_id="Google Search--99")
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "run_package_valid")
                self.assertEqual(verdict["returncode"], 1)

    def test_missing_trajectory_fails(self):
        verdict = self.execute(0, drop_trajectory=True)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "run_package_valid")

    def test_missing_screenshot_fails(self):
        verdict = self.execute(0, break_screenshot=True)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "run_package_valid")

    def test_database_write_fails_content_check(self):
        for task in (0, 21):
            with self.subTest(task=task):
                verdict = self.execute(task, dirty_db=True)
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "db_content_intact")

    def test_tampered_navigation_fails(self):
        """Answer kept, but the answer-page URL rewritten to the homepage."""
        for task in (0, 9, 27, 40):
            with self.subTest(task=task):
                query, _page, answer = POSITIVE[task]
                paths = ["/search?q=" + urllib.parse.quote_plus(query), "/"]
                verdict = self.execute(task, paths=paths, answer=answer)
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "nav_answer_page")
                self.assertEqual(verdict["returncode"], 1)

    def test_task33_requires_the_paste_step(self):
        """Task 33 without the SHA pasted into a textbox must FAIL."""
        verdict = self.execute(33, extra_steps=())
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "answer_sha_pasted_into_textbox")

    def test_task2_accepts_serp_card_headline(self):
        """Task 2's headline also appears as a SERP news card, so the page
        visit is not required there — search + the card headline must PASS."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            initial, after = seed_db(tmp, "initial.db"), seed_db(tmp, "after.db")
            run = make_run(tmp, 2, ["/search?q=" + urllib.parse.quote_plus("Los Angeles Lakers latest news")],
                           "The latest Lakers news title is 'Lakers top Nuggets 112-105' (LeBron James paced the Lakers with 31 points).")
            verdict = run_verifier(2, run, initial, after)
            self.assertTrue(verdict["pass"], verdict)


class AlternateReadingTests(VerifierTests):
    """The dual-reading contracts (tasks 30 and 38): the mirror carries two
    internally consistent page readings and the verifier accepts either."""

    def test_task30_accepts_charts_page_reading(self):
        v = self.execute(
            30,
            paths=["/search?q=" + urllib.parse.quote_plus("Spotify Global Top 50 number one artist"),
                   "/external/charts.spotify.com/charts/view/regional-global-daily/latest"],
            answer="The Spotify Charts page shows Sabrina Carpenter at #1 with 'Espresso', "
                   "followed by Stargazing, Lavender Dreams, Midnight Caller, and Holiday.")
        self.assertTrue(v["pass"], v)

    def test_task30_rejects_mixed_readings(self):
        v = self.execute(
            30,
            paths=["/search?q=" + urllib.parse.quote_plus("Spotify Global Top 50 number one artist"),
                   "/external/charts.spotify.com/charts/view/regional-global-daily/latest"],
            answer="The number-one artist is Bad Bunny with 'Espresso' at #1, followed by "
                   "Stargazing and Lavender Dreams.")
        self.assertFalse(v["pass"])
        self.assertNotEqual(v["reason"], "nav_task_search")

    def test_task38_accepts_timeanddate_reading(self):
        v = self.execute(
            38,
            paths=["/search?q=" + urllib.parse.quote_plus("next visible solar eclipse North America"),
                   "/external/www.timeanddate.com/eclipse/list.html"],
            answer="The next solar eclipse visible in North America is the partial eclipse of "
                   "January 14, 2029 (Saros 151); the next eclipse after that is the partial "
                   "eclipse of June 11, 2029, visible from the Arctic.")
        self.assertTrue(v["pass"], v)

    def test_task38_rejects_page_inconsistent_dates(self):
        v = self.execute(
            38,
            paths=["/search?q=" + urllib.parse.quote_plus("next visible solar eclipse North America"),
                   "/external/www.timeanddate.com/eclipse/list.html"],
            answer="The next solar eclipse visible in North America is the partial eclipse of "
                   "January 14, 2029; the one after that is the partial eclipse of June 12, 2029.")
        self.assertFalse(v["pass"])
        self.assertNotEqual(v["reason"], "nav_task_search")


class ContractTests(unittest.TestCase):
    def test_task_file_carries_verifier_and_rubric_for_every_task(self):
        rows = [json.loads(l) for l in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(len(rows), 43)
        for n, row in enumerate(rows):
            with self.subTest(task=n):
                self.assertEqual(row["id"], f"Google Search--{n}")
                self.assertEqual(row["verifier_path"], f"sites/google_search/verify/verify_{n}.py")
                self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."))
                self.assertIn("MUST", row["judge_rubric"])
                self.assertNotIn("answer", row)

    def test_original_five_keys_unchanged_and_key_order(self):
        orig_keys = ["web_name", "id", "ques", "web", "upstream_url"]
        rows = [json.loads(l) for l in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if l.strip()]
        for n, row in enumerate(rows):
            with self.subTest(task=n):
                self.assertEqual(list(row.keys()), orig_keys + ["verifier_path", "judge_rubric"])
                self.assertEqual(row["web"], "http://localhost:40009/")
                self.assertEqual(row["upstream_url"], "https://www.google.com/")

    def test_verifier_scripts_exist_and_are_deterministic(self):
        for n in TASKS:
            with self.subTest(task=n):
                p = VERIFY_DIR / f"verify_{n}.py"
                self.assertTrue(p.exists())
                src = p.read_text()
                self.assertNotIn("llm_text_match", src)
                self.assertNotIn("llm_screenshot_shows", src)
                self.assertIn("grade_common", src)

    def test_verify_lib_run_package_gate_rejects_broken_runs(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cases = [
                ("missing dir", "missing_dir"),
                ("missing trajectory", "no_traj"),
                ("bad json", "bad_json"),
                ("empty steps", "empty_steps"),
                ("missing screenshot", "missing_shot"),
                ("bad task id", "bad_id"),
                ("bad start url", "bad_start"),
            ]
            for name, kind in cases:
                with self.subTest(case=name):
                    d = tmp / kind
                    if kind != "missing_dir":
                        (d / "screenshots").mkdir(parents=True, exist_ok=True)
                        (d / "screenshots" / "step_000.png").write_bytes(PNG)
                        traj = {"task_id": "Google Search--0", "task": "x",
                                "start_url": ORIGIN + "/", "steps": [
                                    {"step": 0, "url": ORIGIN + "/", "action": "click",
                                     "screenshot_after": "step_000.png"}],
                                "final_answer": "x"}
                        if kind == "no_traj":
                            pass
                        elif kind == "bad_json":
                            (d / "trajectory.json").write_text("{not json")
                        elif kind == "empty_steps":
                            traj["steps"] = []
                            (d / "trajectory.json").write_text(json.dumps(traj))
                        elif kind == "missing_shot":
                            traj["steps"][0]["screenshot_after"] = "step_999.png"
                            (d / "trajectory.json").write_text(json.dumps(traj))
                        elif kind == "bad_id":
                            traj["task_id"] = "Other--0"
                            (d / "trajectory.json").write_text(json.dumps(traj))
                        elif kind == "bad_start":
                            traj["start_url"] = "ftp://x/"
                            (d / "trajectory.json").write_text(json.dumps(traj))
                    old_argv0 = sys.argv[0]
                    sys.argv[0] = str(VERIFY_DIR / "verify_0.py")
                    try:
                        verify_lib.load_run(str(d))
                        self.fail(f"run package gate accepted broken run: {name}")
                    except verify_lib.RunPackageError:
                        pass
                    finally:
                        sys.argv[0] = old_argv0


if __name__ == "__main__":
    unittest.main()
