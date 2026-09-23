"""Deterministic verifier contract tests for the FlightAware mirror.

Covers, per task (0-29):
  - ground-truth sanity against the frozen seed DB (flights, boards, delays,
    cancellation stats, photos, squawks, airports, benchmark users/alerts),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL (contentless answer with homepage-only navigation,
    and the empty-answer variant),
  - a wrong-answer run (correct navigation, false values) MUST FAIL,
  - a shortcut run (ground-truth answer, no navigation to the answer page)
    MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, tiny 1x1 screenshots,
    dropped screenshots, foreign-origin URLs, truncated run, DB drift on a
    read-only task) MUST FAIL,
  - stateful tasks (7, 8, 23): a state-mismatch run (success claimed, DB
    unchanged) MUST FAIL, wrong-mutation runs MUST FAIL, and the honest
    fixture's DB mutation is verified exactly.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed. The seed DB must exist at
sites/flightaware/instance_seed/flightaware.db (regenerated deterministically
by seed_data.py; md5 815bd0d169b1fcd7ebaeca03f281c4ac).
"""
import json
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "flightaware.db"
TASKS = SITE / "tasks.jsonl"
REPO = Path(__file__).resolve().parents[3]
BASE = "http://localhost:40069"

sys.path.insert(0, str(VERIFY))
import grade  # noqa: E402

SEED_MD5 = "815bd0d169b1fcd7ebaeca03f281c4ac"


# ---------------------------------------------------------------- PNG fixture
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def tiny_png():
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00", 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- honest fixtures
def S(url, action="goto", params=None, text=""):
    return (url, action, params or {}, text)


LOGIN = [S(BASE + "/account/login"), S(BASE + "/account/")]

HONEST = {
    0: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=UAL1063"),
                   S(BASE + "/live/flight/UAL1063")],
            answer="United flight UAL1063 (Newark to Mexico City) departed from gate C71. "
                   "Scheduled departure time: 08:28AM EDT. Actual gate departure time: "
                   "08:22AM EDT. Aircraft type operating today's flight: Boeing 737 MAX 8."),
    1: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                   S(BASE + "/live/form.rvt?query=Boston+Logan"),
                   S(BASE + "/live/airport/KBOS"),
                   S(BASE + "/live/airport/KBOS/departures")],
            answer="The first departure listed on the Boston Logan (KBOS) departures board "
                   "is flight RPA5597, aircraft type E75S, destination Jacksonville Intl "
                   "(JAX), departing at 08:58a EDT."),
    2: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=UAL1063"),
                   S(BASE + "/live/flight/UAL1063"),
                   S(BASE + "/live/flight/UAL1063/history")],
            answer="On the UAL1063 flight history page, the flight on September 20, 2026 "
                   "lasted 4h 48m and was operated by the B38M (Boeing 737 MAX 8)."),
    3: dict(steps=[S(BASE + "/"), S(BASE + "/live/airport/delays/")],
            answer="The airport currently experiencing departure delays averaging 50 "
                   "minutes that are decreasing, and arrival delays that are increasing, "
                   "is Manchester (MAN / EGCC)."),
    4: dict(steps=[S(BASE + "/"), S(BASE + "/live/cancelled/")],
            answer="The airline with the most cancelled flights today is PSA Airlines "
                   "(AAL), with 54 cancelled flights, shown as 7%."),
    5: dict(steps=[S(BASE + "/"), S(BASE + "/photos/"),
                   S(BASE + "/photos/all/sort/votes")],
            answer="The photo with the highest number of votes across the whole site is "
                   "\"McDonnell Douglas FA-18 (18-8738)\" by William Gilson, with 850 votes."),
    6: dict(steps=[S(BASE + "/"), S(BASE + "/squawks/"),
                   S(BASE + "/squawks/browse/general/24_hours/most_discussed")],
            answer="The squawk with the most member comments is \"Why Aren’t Passengers "
                   "Who Evacuate With Bags Being Punished?\" with 126 comments, submitted "
                   "by Roger Anderson."),
    7: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                   S(BASE + "/account/alerts/add", "post",
                     {"ident": "BAW117", "alert_type": "basic"}),
                   S(BASE + "/account/")],
            answer="Bob's account now has 4 alerts in total (it had 3 before). The alert "
                   "just created is for flight BAW117 with basic notifications "
                   "(shown as \"BAW117 | basic | just now\")."),
    8: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                   S(BASE + "/account/alerts/3/delete", "post", {"alert_id": 3}),
                   S(BASE + "/account/")],
            answer="After deleting the alert for flight AAL954, Bob's remaining alerts "
                   "are: JBU1024 (basic, about a month ago) and the route alert "
                   "KSFO → RJTT (full, about 5 hours ago)."),
    9: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=EVA17"),
                   S(BASE + "/live/flight/EVA17")],
            answer="Flight EVA17 (San Francisco to Taipei) departed from gate A8, arrives "
                   "at terminal 2, is currently flying at 501 mph (planned speed 564 mph), "
                   "and is operated by the BOEING 777-300ER (B77W)."),
    10: dict(steps=[S(BASE + "/"),
                    S(BASE + "/live/findflight/?origin=Newark&destination=Mexico+City")],
             answer="The Flight Finder shows 1 flight(s) departing Newark and arriving in "
                    "Mexico City: UAL1063."),
    11: dict(steps=[S(BASE + "/"), S(BASE + "/live/fleet/"),
                    S(BASE + "/live/fleet/DAL"), S(BASE + "/live/fleet/"),
                    S(BASE + "/live/fleet/JBU")],
             answer="Delta Air Lines (DAL) has 148 flights tracked today, and JetBlue "
                    "(JBU) has 33 flights tracked today."),
    12: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=JFK"),
                    S(BASE + "/live/airport/KJFK"),
                    S(BASE + "/resources/airport/KJFK/weather")],
             answer="The current weather at JFK: Partly cloudy, Windy, temperature 60 °F."),
    13: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=JFK"),
                    S(BASE + "/live/airport/KJFK"),
                    S(BASE + "/resources/airport/KJFK/remarks")],
             answer="Remark code A110-2 at JFK warns about: \"Flocks of birds on and in "
                    "vicinity of airport.\""),
    14: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                    S(BASE + "/live/form.rvt?query=JFK"),
                    S(BASE + "/live/airport/KJFK"),
                    S(BASE + "/live/airport/KJFK/arrivals")],
             answer="The flight arriving at JFK from Buenos Aires (Ministro Pistarini "
                    "Int'l) is AAL954, aircraft type B772."),
    15: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=AAL169"),
                    S(BASE + "/live/flight/AAL169"),
                    S(BASE + "/live/form.rvt?query=AAL170"),
                    S(BASE + "/live/flight/AAL170")],
             answer="Flight AAL169 departs from Los Angeles (KLAX) and flies to Tokyo "
                    "Haneda (HND); flight AAL170 departs Tokyo Haneda (HND) and arrives "
                    "at Los Angeles (KLAX). Both are operated by the Boeing 787-9 "
                    "Dreamliner (B789)."),
    16: dict(steps=[S(BASE + "/"), S(BASE + "/squawks/")],
             answer="The squawk about a possible meteorite striking a United 737 is "
                    "\"Possible Meteorite Strikes United 737; Injures Pilot\". It links "
                    "to the source domain weatherboy.com (shown in parentheses) and has "
                    "27 member comments."),
    17: dict(steps=[S(BASE + "/"), S(BASE + "/miserymap/")],
             answer="According to the MiseryMap page, the total number of delays within, "
                    "into, or out of the United States today is 938. The airport whose "
                    "arrival delays are increasing is Auckland (AKL / NZAA): arrival "
                    "delays for airborne aircraft an average of 29 minutes (and increasing)."),
    18: dict(steps=[S(BASE + "/"),
                    S(BASE + "/live/form.rvt?query=Singapore+Changi"),
                    S(BASE + "/live/form.rvt?query=Changi")],
             answer="Searching for 'Singapore Changi' matches the airport code SIN "
                    "(Singapore Changi, SIN / SIN). Searching for 'Changi' shows 0 photos "
                    "in the search results (no photos section appears)."),
    19: dict(steps=[S(BASE + "/"), S(BASE + "/photos/"),
                    S(BASE + "/photos/all/sort/votes"),
                    S(BASE + "/photos/view/318841-l%20arge/all/sort/votes/page/1")],
             answer="Photo \"FDX McDonnell Douglas DC-10 (N368FE)\": registration N368FE, "
                    "699 votes (4.85 average), 543,751 views."),
    20: dict(steps=[S(BASE + "/"), S(BASE + "/live/cancelled/")],
             answer="Today there are 537 cancellations worldwide and 183 cancellations "
                    "within, into, or out of the United States."),
    21: dict(steps=[S(BASE + "/"), S(BASE + "/squawks/")],
             answer="The squawk submitted by Amanda Skogstad is \"FlightAware's Role in "
                    "Airspace Modernization\", with the source domain shown in "
                    "parentheses: (blog.flightaware.com)."),
    22: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                    S(BASE + "/live/form.rvt?query=JFK"),
                    S(BASE + "/live/airport/KJFK"),
                    S(BASE + "/live/airport/KJFK/enroute")],
             answer="The flight en route to JFK from Dubai is Emirates UAE203, an A388 "
                    "(Airbus A380-800), expected to arrive at 08:58a EDT."),
    23: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                    S(BASE + "/account/alerts/add", "post",
                      {"origin": "JFK", "destination": "LHR", "alert_type": "full"}),
                    S(BASE + "/account/")],
             answer="Carol's account initially had 1 alert (DAL667, basic). After adding "
                    "a new route alert from JFK to London Heathrow with full "
                    "notifications, the new alert line shows: \"JFK → LHR | full | "
                    "just now\"."),
    24: dict(steps=[S(BASE + "/"), S(BASE + "/account/login"), S(BASE + "/account/"),
                    S(BASE + "/live/form.rvt?query=London+Heathrow"),
                    S(BASE + "/live/airport/EGLL"),
                    S(BASE + "/live/airport/EGLL/departures")],
             answer="The first departure listed on the London Heathrow (EGLL) departures "
                    "board is flight VIR208, aircraft type B789, destination "
                    "Incheon Int'l (ICN), departing at 01:58p BST."),
    25: dict(steps=[S(BASE + "/"), S(BASE + "/live/aircrafttype/"),
                    S(BASE + "/live/aircrafttype/B789")],
             answer="There are 29 Boeing 787-9 Dreamliner (B789) flights tracked today. "
                    "The one departing JFK for London Heathrow is VIR26 (KJFK → LHR, "
                    "08:35a EDT)."),
    26: dict(steps=[S(BASE + "/"), S(BASE + "/photos/"),
                    S(BASE + "/photos/all/sort/votes"),
                    S(BASE + "/photos/all/sort/votes/page/3"),
                    S(BASE + "/photos/view/1463354-e6b1f%20b/all/sort/votes/page/1")],
             answer="The highest-voted photo of a United Boeing 787-9 is \"United B789 "
                    "(N27957)\" — the registration shown in the title is N27957, the "
                    "photographer is Victor Pody, and it has 250 votes."),
    27: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=UAL1063"),
                    S(BASE + "/live/flight/UAL1063")],
             answer="The first four waypoints of the filed route for today's flight "
                    "UAL1063 are: ELVAE NECCK WHITE Q409."),
    28: dict(steps=[S(BASE + "/"), S(BASE + "/live/form.rvt?query=UAL1063"),
                    S(BASE + "/live/flight/UAL1063"),
                    S(BASE + "/live/flight/UAL1063/history")],
             answer="10 of the past flights listed on the UAL1063 history page were "
                    "operated by the Boeing 737 MAX 8 (B38M). The most recent past "
                    "flight date shown is September 21, 2026."),
    29: dict(steps=[S(BASE + "/"), S(BASE + "/squawks/"),
                    S(BASE + "/squawks/search.rvt"),
                    S(BASE + "/squawks/search.rvt?q=meteorite"),
                    S(BASE + "/squawks/search.rvt?q=UPS")],
             answer="Searching squawks for 'meteorite' returns \"Possible Meteorite "
                    "Strikes United 737; Injures Pilot\" with 49 votes. Searching for "
                    "'UPS' returns \"UPS pilots mourn loss of colleagues killed in plane "
                    "crash\"."),
}

WRONG_ANSWERS = {
    0: "United flight UAL1063 departed from gate C72. Scheduled departure 08:32AM EDT; "
       "actual gate departure 08:25AM EDT; aircraft Boeing 737-900.",
    1: "The first KBOS departure is JBU21, an A321 to President Donald J Trump Intl (DJT), "
       "departing 08:56a EDT.",
    2: "The September 20, 2026 UAL1063 flight lasted 4h 55m and was operated by the B738.",
    3: "The airport is Auckland (AKL / NZAA).",
    4: "The airline with the most cancellations is United, with 46 cancelled flights, 1%.",
    5: "The highest-voted photo is \"Airplanes, Airliners, Jets, and more\" by thewingman "
       "with 774 votes.",
    6: "The most-discussed squawk is \"Delta Suspends Congressional Travel Services Amid "
       "Shutdown\" with 46 comments by airguideonline.",
    7: "Bob's account now has 5 alerts; the new one is BAW117 with full notifications.",
    8: "After deleting AAL954, Bob's remaining alerts are DAL667 and UAL1063.",
    9: "EVA17 departed from gate A9, arrives at terminal 1, currently 510 mph (planned "
       "560 mph), operated by the B77L.",
    10: "The Flight Finder shows 2 flights from Newark to Mexico City: UAL1063 and UAL1064.",
    11: "Delta has 147 flights today and JetBlue has 34.",
    12: "JFK weather: Overcast, Light winds, 64 °F.",
    13: "Remark A110-2 warns about: 'Leasee: property owned by city of new york'.",
    14: "The flight from Buenos Aires is AAL955, a B788.",
    15: "AAL169 departs Tokyo Haneda and arrives at Los Angeles; AAL170 departs Los "
       "Angeles for Haneda. Both are Boeing 777-300ER.",
    16: "The meteorite squawk links to aeroxplorer.com and has 25 comments.",
    17: "The total is 1,783 delays, and the airport is Boston Logan (BOS).",
    18: "The airport code is WSSS, and the Changi search shows 3 photos.",
    19: "The DC-10 photo: registration N368FF, 698 votes (4.75 average), 543,752 views.",
    20: "There are 588 cancellations worldwide and 184 in the US.",
    21: "Amanda Skogstad's squawk links to (weatherboy.com).",
    22: "The Dubai flight is Qatari QTR1, a B77W, arriving 09:30a EDT.",
    23: "Carol had 2 alerts; the new line shows JFK → LHR with basic notifications.",
    24: "The first EGLL departure is BAW1484, an A319 to Glasgow Int'l (GLA), at 01:56p BST.",
    25: "There are 30 B789 flights today; the JFK to LHR one is BAW5.",
    26: "The highest-voted United 787-9 photo is by jaxstrw (N827AN) with 0 votes.",
    27: "The first four waypoints are ELVAE NECCK WHITE DEEEZ.",
    28: "9 past flights were operated by the 737 MAX 8; the most recent is September 20, 2026.",
    29: "The meteorite squawk has 48 votes; the UPS search returns \"UPS to add new "
        "freighter routes\".",
}

SHORTCUT_ANSWER_NOTE = "correct answer, homepage-only navigation"


# ---------------------------------------------------------------- run building
def build_run(root, steps, final_answer, n, *, terminated=True, shots_n=None,
              tiny_shots=False, drop_shots=False, no_traj=False, corrupt_traj=False,
              foreign=False, mutate=None, empty_answer=False):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)          # a fresh package: no stale trajectory/shots
    root.mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    if not drop_shots:
        (root / "screenshots").mkdir(exist_ok=True)
        for i in range(frames):
            data = tiny_png() if tiny_shots else make_png(1000 + i)
            (root / "screenshots" / f"step_{i:03d}.png").write_bytes(data)
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    if no_traj:
        return root
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        if foreign:
            url = url.replace(BASE, "https://www.flightaware.com")
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
        "action": "done",
        "params": {"text": "" if empty_answer else final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": CURRENT_TASKS[f"FlightAware--{n}"]["ques"], "task_id": f"FlightAware--{n}",
        "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 40, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": "" if empty_answer else final_answer,
        "success_self_report": True,
        "judge_rubric": "", "verifier_path": f"sites/flightaware/verify/verify_{n}.py",
    }
    text = json.dumps(traj, indent=1)
    if corrupt_traj:
        text = text[: len(text) // 2]
    (root / "trajectory.json").write_text(text)
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=180,
        env={**__import__("os").environ, "WH_SITE": "flightaware"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def _add_bob_baw117(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO alerts (id, user_id, ident, origin_code, dest_code, alert_type, "
        "created_text) VALUES (9, 2, 'BAW117', '', '', 'basic', 'just now')")
    con.commit()
    con.close()


def _delete_bob_aal954(db):
    con = sqlite3.connect(db)
    con.execute("DELETE FROM alerts WHERE id = 3 AND user_id = 2 AND ident = 'AAL954'")
    con.commit()
    con.close()


def _add_carol_route(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO alerts (id, user_id, ident, origin_code, dest_code, alert_type, "
        "created_text) VALUES (9, 3, '', 'JFK', 'LHR', 'full', 'just now')")
    con.commit()
    con.close()


def _add_bob_wrong_type(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO alerts (id, user_id, ident, origin_code, dest_code, alert_type, "
        "created_text) VALUES (9, 2, 'BAW117', '', '', 'full', 'just now')")
    con.commit()
    con.close()


def _add_bob_wrong_ident(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO alerts (id, user_id, ident, origin_code, dest_code, alert_type, "
        "created_text) VALUES (9, 2, 'UAL1063', '', '', 'basic', 'just now')")
    con.commit()
    con.close()


def _delete_bob_wrong_alert(db):
    con = sqlite3.connect(db)
    con.execute("DELETE FROM alerts WHERE id = 4 AND user_id = 2 AND ident = 'JBU1024'")
    con.commit()
    con.close()


def _add_carol_wrong_type(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO alerts (id, user_id, ident, origin_code, dest_code, alert_type, "
        "created_text) VALUES (9, 3, '', 'JFK', 'LHR', 'basic', 'just now')")
    con.commit()
    con.close()


def _extra_user_row(db):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO users (id, username, email, password_hash, display_name) "
        "VALUES (99, 'drift', 'drift@test.com', 'x', 'Drift')")
    con.commit()
    con.close()


# Synthetic component fixtures; actual browser evidence is reviewed separately.
ORIGINAL_HONEST = dict(HONEST)
for number, components in json.loads((VERIFY / 'review_components.json').read_text()).items():
    HONEST[int(number)] = {
        'steps': [step for component in components for step in ORIGINAL_HONEST[component]['steps']],
        'answer': '\n'.join(ORIGINAL_HONEST[component]['answer'] for component in components),
    }
for spec in HONEST.values():
    spec['steps'] = [(url, action, params, text or {
        '/live/airport/KBOS/departures': 'RPA5597 E75S Jacksonville 08:58a',
        '/live/airport/KJFK/arrivals': 'AAL954 B772 Ministro Pistarini',
        '/live/airport/KJFK/enroute': 'UAE203 A388 Dubai 08:58a',
        '/live/airport/EGLL/departures': 'VIR208 B789 Incheon 01:58p',
    }.get(url.replace(BASE, '').rstrip('/'), '')) for url, action, params, text in spec['steps']]

HONEST_MUTATIONS = {7: _add_bob_baw117, 8: _delete_bob_aal954, 23: _add_carol_route}


# Synthetic contract examples for the current coherent tasks; these are not browser recordings.
COHERENT_EXAMPLES = json.loads((VERIFY / 'coherent_examples.json').read_text())
CURRENT_TASKS = {row['id']: row for row in map(json.loads, (VERIFY.parent / 'tasks.jsonl').read_text().splitlines())}
for number, example in COHERENT_EXAMPLES.items():
    HONEST[int(number)] = {'answer': example['answer'], 'steps': [S(BASE + '/', text='Homepage')] +
        [S(BASE + path, text=example['observations']) for path in example['paths']]}

class VerifierContract(unittest.TestCase):
    root = Path("/tmp/wh-fa-verify-tests")

    @classmethod
    def setUpClass(cls):
        if not SEED.is_file():
            raise unittest.SkipTest(f"seed DB missing: {SEED}")
        cls.root.mkdir(parents=True, exist_ok=True)

    def fixture(self, kind, n, **kw):
        spec = HONEST[n]
        steps, answer = spec["steps"], spec["answer"]
        mutate = HONEST_MUTATIONS.get(n) if kind == "honest" else None
        if kind == "noop":
            steps, answer = [S(BASE + "/")], ""
        elif kind == "noop-fake":
            steps, answer = [S(BASE + "/")], spec["answer"]
        elif kind == "wrong":
            answer = WRONG_ANSWERS[n]
        elif kind == "shortcut":
            steps = [S(BASE + "/")]
        elif kind == "shortcut2" and LOGIN[0] in steps:
            steps = [S(BASE + "/"), S(BASE + "/account/login")]
        if mutate and "mutate" not in kw:
            kw["mutate"] = mutate
        run = build_run(self.root / f"{kind}-{n}", steps, answer, n, **kw)
        return run

    # ---------------------------------------------------------------- contract
    def test_tasks_jsonl_contract(self):
        rows = [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 30)
        expected_keys = {"web_name", "id", "ques", "web", "upstream_url",
                         "verifier_path", "judge_rubric"}
        for i, row in enumerate(rows):
            with self.subTest(row=i):
                self.assertEqual(set(row), expected_keys)
                self.assertNotIn("answer", row)
                self.assertEqual(row["id"], f"FlightAware--{i}")
                self.assertEqual(row["verifier_path"],
                                 f"sites/flightaware/verify/verify_{i}.py")
                self.assertTrue((REPO / row["verifier_path"]).is_file(),
                                row["verifier_path"])
                self.assertTrue(row["judge_rubric"].strip())
                self.assertIn("FAIL", row["judge_rubric"])

    def test_verifier_files_exist(self):
        for n in range(30):
            self.assertTrue((VERIFY / f"verify_{n}.py").is_file(), n)
        self.assertTrue((VERIFY / "verify_lib.py").is_file())
        self.assertTrue((VERIFY / "grade.py").is_file())

    # ------------------------------------------------- ground truth vs seed DB
    def test_reviewed_seed_contents(self):
        from composed_grade import fixture_hashes
        expected = json.loads((VERIFY / 'reviewed_seed.json').read_text())
        self.assertEqual(fixture_hashes(SEED), expected)

    def test_ground_truth_matches_seed_db(self):
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row

        def one(sql, params=()):
            rows = con.execute(sql, params).fetchall()
            self.assertEqual(len(rows), 1, sql)
            return rows[0]

        # counts
        self.assertEqual(one("SELECT COUNT(*) c FROM airports")["c"], 395)
        self.assertEqual(one("SELECT COUNT(*) c FROM flights")["c"], 1726)
        self.assertEqual(one("SELECT COUNT(*) c FROM photos")["c"], 79)
        self.assertEqual(one("SELECT COUNT(*) c FROM squawks")["c"], 14)

        # T0 / T27: UAL1063 today
        f = one("SELECT * FROM flights WHERE ident='UAL1063' AND flight_date='2026-09-22'")
        self.assertEqual(f["gate_dep"], "C71")
        self.assertEqual(f["sched_dep"], "08:28AM EDT")
        self.assertEqual(f["actual_dep"], "08:22AM EDT")
        self.assertEqual(f["aircraft_type"], "B38M")
        self.assertEqual(f["route"].split()[:4], ["ELVAE", "NECCK", "WHITE", "Q409"])

        # T2 / T28: UAL1063 history
        h = one("SELECT * FROM flights WHERE ident='UAL1063' AND flight_date='2026-09-20'")
        self.assertEqual(h["duration_text"], "4h 48m")
        self.assertEqual(h["aircraft_type"], "B38M")
        past = con.execute("SELECT flight_date, aircraft_type FROM flights WHERE "
                           "ident='UAL1063' AND flight_date < '2026-09-22'").fetchall()
        self.assertEqual(len(past), 10)
        self.assertTrue(all(r["aircraft_type"] == "B38M" for r in past))
        self.assertEqual(max(r["flight_date"] for r in past), "2026-09-21")

        # T9: EVA17
        f = one("SELECT * FROM flights WHERE ident='EVA17' AND is_today=1")
        self.assertEqual((f["gate_dep"], f["arr_terminal"], f["speed_mph"],
                          f["planned_speed_mph"], f["aircraft_type"]),
                         ("A8", "2", 501, 564, "B77W"))

        # T15: AAL169 / AAL170
        f1 = one("SELECT * FROM flights WHERE ident='AAL169' AND is_today=1")
        f2 = one("SELECT * FROM flights WHERE ident='AAL170' AND is_today=1")
        self.assertEqual((f1["origin_code"], f1["dest_code"], f1["aircraft_type"]),
                         ("KLAX", "HND", "B789"))
        self.assertEqual((f2["origin_code"], f2["dest_code"], f2["aircraft_type"]),
                         ("HND", "KLAX", "B789"))

        # T1: KBOS departures first row
        r = one("SELECT * FROM board_rows WHERE airport_code='KBOS' AND "
                "board='departures' ORDER BY row_index LIMIT 1")
        self.assertEqual((r["ident"], r["aircraft_type"], r["other_label"], r["dep_text"]),
                         ("RPA5597", "E75S", "Jacksonville Intl (JAX)", "08:58a EDT"))

        # T14: KJFK arrivals EZE
        r = one("SELECT * FROM board_rows WHERE airport_code='KJFK' AND board='arrivals' "
                "AND other_label LIKE '%Pistarini%'")
        self.assertEqual((r["ident"], r["aircraft_type"]), ("AAL954", "B772"))

        # T22: KJFK enroute DXB
        r = one("SELECT * FROM board_rows WHERE airport_code='KJFK' AND board='enroute' "
                "AND other_label LIKE '%Dubai%'")
        self.assertEqual((r["ident"], r["aircraft_type"]), ("UAE203", "A388"))
        self.assertEqual(r["arr_text"], "08:58a EDT")

        # T24: EGLL departures first row
        r = one("SELECT * FROM board_rows WHERE airport_code='EGLL' AND "
                "board='departures' ORDER BY row_index LIMIT 1")
        self.assertEqual((r["ident"], r["aircraft_type"]), ("VIR208", "B789"))
        self.assertEqual(r["other_label"], "Incheon Int'l (ICN)")
        self.assertEqual(r["dep_text"], "01:58p BST")

        # T3 / T17: delays
        d = one("SELECT * FROM airport_delays WHERE airport_label LIKE 'Manchester%'")
        self.assertIn("50 minutes", d["dep_delay_text"])
        self.assertIn("decreasing", d["dep_delay_text"])
        self.assertIn("increasing", d["arr_delay_text"])
        a = one("SELECT * FROM airport_delays WHERE airport_label LIKE 'Auckland%'")
        self.assertIn("increasing", a["arr_delay_text"])
        s = one("SELECT value_int FROM daily_stats WHERE key='us_delays_today'")
        self.assertEqual(s["value_int"], 938)

        # T4 / T20: cancellation stats
        c = one("SELECT * FROM cancel_stats WHERE scope='airline' "
                "ORDER BY cancelled DESC LIMIT 1")
        self.assertEqual((c["label"], c["cancelled"], c["cancelled_pct"]),
                         ("PSA Airlines (AAL)", 54, "7%"))
        w = one("SELECT value_int FROM daily_stats WHERE key='world_cancel_today'")
        u = one("SELECT value_int FROM daily_stats WHERE key='us_cancel_today'")
        self.assertEqual((w["value_int"], u["value_int"]), (537, 183))

        # T5 / T19 / T26: photos
        p = one("SELECT * FROM photos ORDER BY votes DESC LIMIT 1")
        self.assertEqual((p["title"], p["photographer"], p["votes"]),
                         ("McDonnell Douglas FA-18 (18-8738)", "William Gilson", 850))
        p = one("SELECT * FROM photos WHERE pid='318841'")
        self.assertEqual((p["registration"], p["votes"], p["vote_average"], p["views"]),
                         ("N368FE", 699, 4.85, 543751))
        p = one("SELECT * FROM photos WHERE pid='1463354'")
        self.assertEqual((p["title"], p["registration"], p["photographer"], p["votes"]),
                         ("United B789 (N27957)", "N27957", "Victor Pody", 250))
        ua789 = con.execute("SELECT title, votes FROM photos WHERE aircraft_type='B789' "
                            "AND (airline_prefix='United' OR title LIKE '%United%') "
                            "ORDER BY votes DESC").fetchall()
        self.assertEqual(len(ua789), 1)
        self.assertEqual(ua789[0]["votes"], 250)

        # T6 / T16 / T21 / T29: squawks
        q = one("SELECT * FROM squawks ORDER BY comment_count DESC LIMIT 1")
        self.assertEqual((q["title"], q["comment_count"], q["submitter"]),
                         ("Why Aren’t Passengers Who Evacuate With Bags Being Punished?",
                          126, "Roger Anderson"))
        q = one("SELECT * FROM squawks WHERE title LIKE '%Meteorite%'")
        self.assertEqual((q["source_label"], q["comment_count"], q["votes"]),
                         ("(weatherboy.com)", 27, 49))
        q = one("SELECT * FROM squawks WHERE submitter='Amanda Skogstad'")
        self.assertEqual((q["title"], q["source_label"]),
                         ("FlightAware's Role in Airspace Modernization",
                          "(blog.flightaware.com)"))
        q = one("SELECT * FROM squawks WHERE title LIKE 'UPS pilots mourn%'")
        self.assertEqual(q["votes"], 38)

        # T10: EWR -> MEX today
        rows = con.execute("SELECT ident FROM flights WHERE is_today=1 "
                           "AND origin_code='KEWR' AND dest_code='MEX'").fetchall()
        self.assertEqual([r["ident"] for r in rows], ["UAL1063"])

        # T11: DAL / JBU counts
        self.assertEqual(one("SELECT COUNT(*) c FROM flights WHERE is_today=1 "
                             "AND airline_code='DAL'")["c"], 148)
        self.assertEqual(one("SELECT COUNT(*) c FROM flights WHERE is_today=1 "
                             "AND airline_code='JBU'")["c"], 33)

        # T25: B789 count + VIR26
        self.assertEqual(one("SELECT COUNT(*) c FROM flights WHERE is_today=1 "
                             "AND aircraft_type='B789'")["c"], 29)
        v = one("SELECT * FROM flights WHERE ident='VIR26' AND is_today=1")
        self.assertEqual((v["origin_code"], v["dest_code"]), ("KJFK", "LHR"))

        # T12 / T13: KJFK weather + remarks
        ap = one("SELECT * FROM airports WHERE code='KJFK'")
        self.assertEqual(ap["weather_text"], "Partly cloudy\nWindy\n60 °F")
        self.assertIn("A110-2\tFlocks of birds on and in vicinity of airport.",
                      ap["remarks_text"])

        # T18: SIN + zero Changi photos
        ap = one("SELECT * FROM airports WHERE name='Singapore Changi'")
        self.assertEqual(ap["code"], "SIN")
        n = con.execute("SELECT COUNT(*) c FROM photos WHERE title LIKE '%Changi%' "
                        "OR airport_code LIKE '%SIN%' OR airport_code LIKE '%WSSS%'").fetchone()
        self.assertEqual(n["c"], 0)

        # T7 / T8 / T23: users + alerts
        self.assertEqual(one("SELECT COUNT(*) c FROM users")["c"], 4)
        bob = con.execute("SELECT * FROM alerts WHERE user_id=2 ORDER BY id").fetchall()
        self.assertEqual(len(bob), 3)
        self.assertEqual([a["ident"] for a in bob if a["ident"]],
                         ["AAL954", "JBU1024"])
        self.assertEqual(bob[2]["origin_code"], "KSFO")
        carol = con.execute("SELECT * FROM alerts WHERE user_id=3").fetchall()
        self.assertEqual(len(carol), 1)
        self.assertEqual((carol[0]["ident"], carol[0]["alert_type"]), ("DAL667", "basic"))
        con.close()

    # ---------------------------------------------------------- honest mutations
    def test_honest_mutation_is_exactly_the_task_outcome(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            after = Path(tmp) / "after.db"
            shutil.copy2(SEED, after)
            HONEST_MUTATIONS[7](after)
            con = sqlite3.connect(f"file:{after}?mode=ro", uri=True)
            rows = con.execute("SELECT ident, alert_type, origin_code, dest_code FROM "
                               "alerts WHERE user_id=2 ORDER BY id").fetchall()
            con.close()
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[-1], ("BAW117", "basic", "", ""))
        with tempfile.TemporaryDirectory() as tmp:
            after = Path(tmp) / "after.db"
            shutil.copy2(SEED, after)
            HONEST_MUTATIONS[8](after)
            con = sqlite3.connect(f"file:{after}?mode=ro", uri=True)
            idents = [r[0] for r in con.execute("SELECT ident FROM alerts WHERE "
                                                "user_id=2 ORDER BY id").fetchall()]
            con.close()
            self.assertEqual(idents, ["JBU1024", ""])
        with tempfile.TemporaryDirectory() as tmp:
            after = Path(tmp) / "after.db"
            shutil.copy2(SEED, after)
            HONEST_MUTATIONS[23](after)
            con = sqlite3.connect(f"file:{after}?mode=ro", uri=True)
            rows = con.execute("SELECT origin_code, dest_code, alert_type FROM alerts "
                               "WHERE user_id=3 ORDER BY id").fetchall()
            con.close()
            self.assertEqual(rows, [("", "", "basic"), ("JFK", "LHR", "full")])

    # -------------------------------------------------------- per-task matrices
    def test_honest_run_passes(self):
        for n in range(30):
            with self.subTest(task=n):
                run = self.fixture("honest", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), True,
                                 f"honest run must pass: {verdict.get('reason')} "
                                 f"{verdict.get('evidence')}")
                self.assertEqual(rc, 0)

    def test_noop_run_fails(self):
        for n in range(30):
            with self.subTest(task=n):
                run = self.fixture("noop", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False, f"no-op must fail: {n}")
                self.assertEqual(rc, 1)

    def test_homepage_fake_answer_fails(self):
        for n in range(30):
            with self.subTest(task=n):
                run = self.fixture("noop-fake", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"homepage + correct answer must fail (shortcut): {n}")
                self.assertNotEqual(verdict.get("reason"), "run_complete")

    def test_wrong_answer_fails(self):
        for n in range(30):
            with self.subTest(task=n):
                run = self.fixture("wrong", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"wrong answer must fail: {n} "
                                 f"{verdict.get('reason')}")
                self.assertEqual(rc, 1)

    def test_shortcut_run_fails(self):
        for n in range(30):
            with self.subTest(task=n):
                run = self.fixture("shortcut", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"shortcut must fail: {n} {verdict.get('reason')}")
                self.assertTrue(verdict.get("reason", "").startswith(("nav_", "ans_", "shot_")),
                                f"shortcut failure must be a navigation/answer/shot anchor: "
                                f"{verdict.get('reason')}")

    def test_tampered_packages_fail(self):
        variants = {
            "no_trajectory": dict(no_traj=True),
            "corrupt_trajectory": dict(corrupt_traj=True),
            "tiny_screenshots": dict(tiny_shots=True),
            "dropped_screenshots": dict(drop_shots=True),
            "foreign_origin": dict(foreign=True),
            "truncated_run": dict(terminated=False),
        }
        for name, kw in variants.items():
            for n in range(30):
                with self.subTest(variant=name, task=n):
                    run = self.fixture("honest", n, **kw)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                     f"{name} must fail: task {n} {verdict.get('reason')}")

    def test_db_drift_on_readonly_fails(self):
        for n in sorted(grade.READONLY):
            with self.subTest(task=n):
                run = self.fixture("honest", n, mutate=_extra_user_row)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"read-only task DB drift must fail: {n}")
                self.assertEqual(verdict.get("reason"), "db_readonly")

    def test_state_mismatch_fails(self):
        for n in sorted(grade.STATEFUL):
            with self.subTest(task=n):
                run = self.fixture("honest-nomut", n)   # no mutation: DB unchanged
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"state mismatch must fail: {n} {verdict.get('reason')}")
                self.assertIn(verdict.get("reason"),
                              ("db_alert_added", "db_new_alert_row", "db_alert_deleted",
                               "db_others_unchanged"))

    def test_wrong_mutation_fails(self):
        wrong_mutations = {
            7: [_add_bob_wrong_type, _add_bob_wrong_ident],
            8: [_delete_bob_wrong_alert],
            23: [_add_carol_wrong_type],
        }
        for n, mutators in wrong_mutations.items():
            for mut in mutators:
                with self.subTest(task=n, mutator=mut.__name__):
                    run = self.fixture("honest", n, mutate=mut)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                     f"wrong mutation must fail: {n} {mut.__name__} "
                                     f"{verdict.get('reason')}")

    def test_stateful_extra_drift_fails(self):
        def mutate_and_drift(db):
            HONEST_MUTATIONS[7](db)
            _extra_user_row(db)
        run = self.fixture("honest", 7, mutate=mutate_and_drift)
        rc, verdict = run_verifier(7, run)
        self.assertEqual(verdict.get("pass"), False)
        self.assertEqual(verdict.get("reason"), "db_others_unchanged")


if __name__ == "__main__":
    unittest.main()
