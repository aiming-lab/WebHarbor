"""Shared fixture builders for the re_max verifier tests (self-contained).

Fixtures are BUILT at test time — no machine-local paths outside the repo:

  * the frozen seed DB is fetched from the review container (docker cp),
    or taken from the ``RE_MAX_TEST_SEED_DB`` env var when set;
  * honest trajectories come from the embedded ``_walks.py`` data (recorded
    from the real 2026-09-25 audit browser walkthroughs; 20/20 verifier
    PASS) plus the frozen honest answers below;
  * screenshots are tiny generated PNGs (the contract only requires
    decodable PNG evidence);
  * stateful after-DBs are derived from the seed with the exact sqlite
    mutations the honest runs performed.

Adversarial fixtures derive from the honest ones by mutating exactly one
thing: the final answer, the navigation, the after-DB, or the trajectory
identity. No LLM. Run with plain python3 + pytest:

    python3 -m pytest sites/re_max/verify/tests -q
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
sys.path.insert(0, str(HERE))
from _walks import WALKS  # noqa: E402

START = 'http://127.0.0.1:40090/'
CONTAINER = os.environ.get('RE_MAX_TEST_CONTAINER', 'wh-remax-review')
FIXTURES = Path(tempfile.mkdtemp(prefix='remax-verify-tests-'))
_SEED_CACHE = Path(tempfile.gettempdir()) / 'remax_verify_tests_seed.db'

# r2 (c5ef103e): T15 (newsletter signup) and T18 (tour request) became
# stateful; T8/T9/T10 deltas re-anchored with the deepened tasks
READ_ONLY = [t for t in range(20) if t not in (4, 8, 9, 10, 11, 12, 13, 15, 18)]
STATEFUL = [4, 8, 9, 10, 11, 12, 13, 15, 18]


# ------------------------------------------------------------- seed plumbing
def _acquire_seed() -> Path:
    env = Path(os.environ.get('RE_MAX_TEST_SEED_DB') or '')
    if env.is_file():
        return env
    if not _SEED_CACHE.is_file():
        out = subprocess.run(
            ['docker', 'cp',
             f'{CONTAINER}:/opt/WebSyn/re_max/instance_seed/re_max.db',
             str(_SEED_CACHE)],
            capture_output=True, timeout=180)
        if out.returncode != 0:
            raise RuntimeError(
                f'cannot fetch the seed DB from container {CONTAINER!r}: '
                f'{out.stderr.decode()[:200]}. Set RE_MAX_TEST_SEED_DB to a '
                f'seed DB path to run without docker.')
    return _SEED_CACHE


def _tiny_png(w=4, h=4):
    raw = b''.join(b'\x00' + b'\x40\x90\xd0' * w for _ in range(h))

    def chunk(tag, data):
        return (len(data).to_bytes(4, 'big') + tag + data
                + zlib.crc32(tag + data).to_bytes(4, 'big'))

    ihdr = w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + b'\x08\x02\x00\x00\x00'
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + zlib.compress(raw) + chunk(b'IEND', b''))


PNG = _tiny_png()


# ------------------------------------------------- stateful after-DB deltas
_TS = '2026-09-25 12:00'


def _mutate_after_db(db_path, task):
    """Apply the exact sqlite delta the honest walkthrough performed."""
    con = sqlite3.connect(db_path)
    try:
        if task == 4:
            con.execute(
                "INSERT INTO inquiries (user_id, listing_id, kind, name, "
                "email, phone, message, created_at) VALUES "
                "(NULL, 372, 'tour', 'Bellevue Tour Guest', "
                "'bellevue.tour@example.com', NULL, 'I would like to tour "
                "this home during its open house.', ?)", (_TS,))
        elif task == 8:
            con.execute(
                "INSERT INTO inquiries (user_id, rental_id, kind, name, "
                "email, phone, message, created_at) VALUES "
                "(NULL, 2, 'listing', 'Renter Family', "
                "'renter.family@example.com', NULL, 'Is this rental still "
                "available?', ?)", (_TS,))
        elif task == 9:
            con.execute(
                "INSERT INTO inquiries (user_id, rental_id, kind, name, "
                "email, phone, message, created_at) VALUES "
                "(NULL, 37, 'tour', 'Mover Reloc', "
                "'mover.reloc@example.com', NULL, 'I would like to schedule "
                "a tour of this rental.', ?)", (_TS,))
        elif task == 10:
            con.execute("DELETE FROM favorites WHERE id = 4")          # 2707 E Side Dr
            con.execute(
                "INSERT INTO favorites (user_id, listing_id, created_at) "
                "VALUES (2, 279, ?)", (_TS,))                          # 8525 Birmingham Dr
            con.execute("DELETE FROM saved_searches WHERE id = 3")     # Denver townhouses
        elif task == 11:
            con.execute("DELETE FROM favorites WHERE id IN (10, 11)")  # Naples pair
            con.execute(
                "INSERT INTO saved_searches (user_id, name, city, state, "
                "home_type, min_price, max_price, beds, created_at) "
                "VALUES (3, 'Miami, FL', 'Miami', 'FL', 'Condo', NULL, "
                "400000, NULL, ?)", (_TS,))
        elif task == 12:
            con.execute(
                "INSERT INTO users (username, email, first_name, last_name, "
                "display_name, password_hash, buyer_type, phone, created_at) "
                "VALUES ('maria_torres', 'maria.torres@example.com', 'Maria', "
                "'Torres', 'Maria Torres', 'pbkdf2:sha256:260000$test$test', "
                "'Downsizer', '(305) 555-0134', ?)", (_TS,))
            uid = con.execute(
                "SELECT id FROM users WHERE email = "
                "'maria.torres@example.com'").fetchone()[0]
            con.execute(
                "INSERT INTO listing_alerts (user_id, email, city, state, "
                "created_at) VALUES (?, 'maria.torres@example.com', 'Miami', "
                "'FL', ?)", (uid, _TS))
        elif task == 13:
            con.execute(
                "INSERT INTO inquiries (user_id, agent_id, kind, name, "
                "email, phone, message, created_at) VALUES "
                "(NULL, 16, 'agent', 'Solar Seller', "
                "'solar.seller@example.com', NULL, \"I'm asking about "
                "selling a house with solar panels.\", ?)", (_TS,))
        elif task == 15:
            con.execute(
                "INSERT INTO newsletter_subscribers (email, buyer_type, "
                "created_at) VALUES ('rate.watcher@example.com', "
                "'Move-up buyer', ?)", (_TS,))
        elif task == 18:
            con.execute(
                "INSERT INTO inquiries (user_id, listing_id, kind, name, "
                "email, phone, message, created_at) VALUES "
                "(NULL, 286, 'tour', 'Pat Rivera', "
                "'calistoga.tour@example.com', '(512) 555-0184', 'I would "
                "like to request a tour of this home.', ?)", (_TS,))
        else:
            return  # read-only task: after == seed
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------- honest fixtures
def _norm_url(u):
    """Rewrite a recorded walk URL onto the canonical START origin."""
    u = str(u)
    if '/static/' in u or u.endswith(('.css', '.js', '.svg')):
        return u
    i = u.find('/', len('http://'))
    if i == -1:
        return START
    return START[:-1] + u[i:]


def _write_traj(run_dir, task, steps, answer):
    shots = run_dir / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    n = len(steps)
    for i in range(n + 1):
        (shots / f'step_{i:03d}.png').write_bytes(PNG)
    traj_steps = []
    for i, (url, fill) in enumerate(steps):
        action = 'fill' if fill is not None else 'goto'
        traj_steps.append({
            'step': i, 'url': url, 'title': 'REMAX',
            'thought': 'honest walkthrough step', 'action': action,
            'params': {'text': fill} if fill is not None else {},
            'observed_text': 'live',
            'screenshot_before': f'step_{i:03d}.png',
            'screenshot_after': f'step_{i + 1:03d}.png'})
    traj = {'task': f'REMAX--{task} honest fixture', 'task_id': f'REMAX--{task}',
            'start_url': START, 'model': 'audit', 'max_steps': 200,
            'steps': traj_steps, 'terminated': True,
            'termination_reason': 'agent_done', 'final_answer': answer,
            'judge_rubric': '', 'verifier_path': '',
            'final_url': steps[-1][0] if steps else START,
            'success_self_report': True}
    (run_dir / 'trajectory.json').write_text(json.dumps(traj, indent=1))


def honest_dir(task):
    """Build (once) the honest fixture for a task from the embedded walk."""
    d = FIXTURES / f'honest_{task}'
    if (d / 'trajectory.json').is_file():
        return d
    d.mkdir(parents=True, exist_ok=True)
    seed = _acquire_seed()
    shutil.copyfile(seed, d / 'initial.db')
    shutil.copyfile(seed, d / 'after.db')
    _mutate_after_db(d / 'after.db', task)
    steps = [(_norm_url(u), f) for u, f in WALKS[str(task)]]
    _write_traj(d, task, steps, HONEST_ANSWERS[task])
    return d


# ------------------------------------------------------- adversarial clones
def run_verifier(task, run_dir):
    """Run verify_<task>.py against run_dir; returns (exit_code, verdict)."""
    proc = subprocess.run(
        [sys.executable, str(VERIFY_DIR / f'verify_{task}.py'),
         '--run_dir', str(run_dir)],
        capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        verdict = {'pass': False, 'reason': 'unparseable output: ' + proc.stdout[:200]}
    return proc.returncode, verdict


def clone(src, dst):
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def set_answer(run_dir, answer):
    p = Path(run_dir) / 'trajectory.json'
    traj = json.loads(p.read_text())
    traj['final_answer'] = answer
    p.write_text(json.dumps(traj, indent=1))


def set_steps(run_dir, steps):
    p = Path(run_dir) / 'trajectory.json'
    traj = json.loads(p.read_text())
    traj['steps'] = steps
    traj['final_url'] = steps[-1]['url'] if steps else START
    p.write_text(json.dumps(traj, indent=1))


def mutate_db(run_dir, sql, args=()):
    p = Path(run_dir) / 'after.db'
    con = sqlite3.connect(p)
    con.execute(sql, args)
    con.commit()
    con.close()


def noop_fixture(task):
    """Homepage only, empty answer, clean DB."""
    d = clone(honest_dir(task), FIXTURES / f'noop_{task}')
    set_steps(d, [{'action': 'navigate', 'url': START, 'params': {}}])
    set_answer(d, '')
    return d


def shortcut_fixture(task):
    """Correct answer, but the agent never left the homepage."""
    d = clone(honest_dir(task), FIXTURES / f'shortcut_{task}')
    set_steps(d, [{'action': 'navigate', 'url': START, 'params': {}}])
    set_answer(d, HONEST_ANSWERS[task])
    return d


def wrong_answer_fixture(task):
    """Honest navigation, but every number/name in the answer is wrong."""
    d = clone(honest_dir(task), FIXTURES / f'wrong_{task}')
    set_answer(d, WRONG_ANSWERS[task])
    return d


def mutated_db_fixture(task):
    """Read-only task: the after-DB has one row mutated (agent claims success
    but the DB was touched)."""
    d = clone(honest_dir(task), FIXTURES / f'mutdb_{task}')
    mutate_db(d, "UPDATE listings SET price = price + 1 WHERE id = 273")
    return d


def state_mismatch_fixture(task):
    """Stateful task: the DB shows no trace of the required action."""
    d = clone(honest_dir(task), FIXTURES / f'stattemismatch_{task}')
    # revert the after-DB to the pristine seed: agent self-reports success but
    # the state change is absent
    shutil.copyfile(d / 'initial.db', d / 'after.db')
    return d


def tamper_fixture(task, kind):
    d = clone(honest_dir(task), FIXTURES / f'tamper_{task}_{kind}')
    p = d / 'trajectory.json'
    traj = json.loads(p.read_text())
    if kind == 'task_id':
        traj['task_id'] = 'REMAX--999'
    elif kind == 'offsite_url':
        traj['steps'].append({'action': 'navigate',
                              'url': 'https://example.com/leak', 'params': {}})
    elif kind == 'not_terminated':
        traj['terminated'] = False
        traj['termination_reason'] = 'max_steps'
    elif kind == 'empty_answer':
        traj['final_answer'] = ''
    elif kind == 'corrupt_png':
        shots = sorted((d / 'screenshots').glob('step_*.png'))
        if shots:
            shots[0].write_bytes(b'not a png')
    p.write_text(json.dumps(traj, indent=1))
    return d


HONEST_ANSWERS = {
    0: "17 Chandon Ln is the cheapest match: built in 2007, $251 per square foot, and a $700 quarterly HOA fee, with an open house Saturday September 26th 2-4pm. 8309 Pompano Cv's open house is Sunday September 27th 11:3-2pm and 4602 Trail Crest Cir's is Saturday September 26th 11-1pm.",
    1: "6439 139th Ave NE Apt 19 has an open house on Sunday September 27th, 3-5pm; 7525 Old Redmond Rd # 403 has no open house scheduled. The cheaper one (6439 139th Ave NE Apt 19) is $446 per square foot with 1 parking space.",
    2: "16530 NE 99th St is the newest-built Redmond home (2026). It is presented by REMAX Eastside Brokers Inc, at $727 per square foot, with 3 parking spaces.",
    3: "4867 Painted Sky VW in Colorado Springs gives more square footage per dollar: $156 per square foot, built 2026, with 1 parking space. It is $222 per square foot cheaper than the most expensive of the four, 3437 W 63rd Pl at $378 per square foot.",
    4: "I picked 1003 156th Ave NE Unit 308 at $405,000 with an open house Saturday September 26th 1-3pm, and requested a tour with bellevue.tour@example.com.",
    5: "Wesley Hardin is the Spanish-speaking agent; his office is in Aurora, he has 28 years of experience, one of his hobbies is Sports, and his license number is FA40014061. Across the directory 7 agents have 30 or more years of experience, and the most experienced is Ivy Boland with 50 years.",
    6: "Scott Eoff is the most experienced Illinois-licensed agent, a Managing Broker with 24 years, with the Chamber of Commerce among his civic activities. Maureen Petrucci is the most experienced Pennsylvania agent with 43 years, and there are 2 Pennsylvania agents.",
    7: "REMAX DFW Associates I serves Grapevine; its website is www.yourhometownpro.com, staff speak Hindi and Spanish besides English, and it also serves Flower Mound. 1 of the 5 Hindi-language offices has Dallas in its service areas, and the site's search finds 1 office for Grapevine.",
    8: "15 rentals match. The most recently built is 217 Bay Pine Dr, Madison at $1,850 a month (built 2024); I asked about availability with renter.family@example.com and the site said an agent will contact me.",
    9: "Louisville's cheapest three-bedroom ($1,400, 2110 Burwell Ave) is $600 per month cheaper than Worcester's ($2,000, 53 Ellsworth St Apt 3). 2110 Burwell Ave's description mentions a basement. I scheduled a tour on 2110 Burwell Ave with mover.reloc@example.com and the site confirmed the tour request.",
    10: "Bob now has 4 favorites and the new most expensive one is $799,990; 1 saved search remains (the Austin houses search).",
    11: "The site named the saved search \"Miami, FL\" and 2 favorites remain.",
    12: "The account overview shows buyer type Downsizer and phone (305) 555-0134.",
    13: "The Florida agents' years of experience: Patrick Kavanagh 33, Nathan Berlin 13, Deirdre Hecht 3. Nathan Berlin is the Broker / Owner; his civic activities include Children's Miracle Network, and the site confirmed the message has been sent to him.",
    14: "Conventional caps run from 2% to 9%, FHA and USDA cap at 6%, and concessions cannot cover the down payment. The first-time buyer article cites a median sales price of $450,000. 5 Naples homes match under $500,000 with 2+ beds and 2+ baths; the cheapest is 315 Saint Andrews Blvd Apt D31 at $220,000, built 1977, $195 per square foot.",
    15: "The Fed raised the federal funds rate to 3.75% to 4% by a 12-0 vote at its September 15-16, 2026 meeting. The HomeHQ newsletter signup with rate.watcher@example.com was confirmed. 6 Chicago homes match under $500,000 with 3+ beds; the cheapest is $299,900.",
    16: "37 luxury properties are listed in total. The cheapest Florida luxury home is 5759 SW 42nd St at $2,350,000; the cheapest Washington luxury home is 12290 235th Pl NE at $2,050,000. 1 Miami home matches at $2,000,000+ with 4+ beds, priced $2,350,000; 2 Seattle homes match at $2,000,000+, the most expensive being $2,595,000.",
    17: "Phoenix has the most Arizona listings (20). 3 open-house houses with 2+ baths match there; the cheapest is 22627 N 31st Ave at $589,700, open houses Friday September 25th 4-7pm and Saturday September 26th 10-1pm, $320 per square foot, built 1993.",
    18: "12609 Calistoga Way is $850,000 with 5 bedrooms and 4 bathrooms, $236 per square foot, a $100.50 monthly HOA fee, and an open house Saturday September 26th 11-1am. 2450 Wickersham Ln Apt 1402 is $177 per square foot with a $351 monthly HOA fee. 1914 Alegria Rd is $1,085,000 with an open house Saturday September 26th 11-1pm. I requested a tour of the Calistoga Way home as Pat Rivera and the site confirmed the tour request.",
    19: "Denver has the most open houses (6). 4 of them are open on Saturday, September 26th; the earliest opener that day is 2363 W 118th Ave (10-1pm). The price range of all the matches is $422,000 to $1,470,000.",
}

# deliberately wrong-but-plausible answers (same shape, wrong facts)
WRONG_ANSWERS = {
    0: "17 Chandon Ln is the cheapest match: built in 2015, $310 per square foot, and a $450 monthly HOA fee, with an open house Sunday 12-2pm. 8309 Pompano Cv's open house is Monday 9-11am and 4602 Trail Crest Cir's is Friday 2-4pm.",
    1: "6439 139th Ave NE Apt 19 has an open house on Saturday October 3rd, 10am-12pm; 7525 Old Redmond Rd # 403 has an open house Sunday 1-3pm. The cheaper one is $512 per square foot with 2 parking spaces.",
    2: "18316 NE 111th St is the newest-built Redmond home. It is presented by REMAX First Shot, at $512 per square foot, with 2 parking spaces.",
    3: "3545 Clubheights Dr in Colorado Springs gives more square footage per dollar: $289 per square foot, built 1990, with 3 parking spaces. It is $95 per square foot cheaper than the most expensive of the four.",
    4: "I picked 2680 139th Ave SE Apt 60 at $780,000 with an open house Saturday 12-2pm, and requested a tour.",
    5: "Alisha Richardson is the Spanish-speaking agent; her office is in Wilmington, she has 22 years of experience, one of her hobbies is Golf, and her license number is FA12345678. 4 agents have 30 or more years of experience, and the most experienced is James Wilcox with 35 years.",
    6: "Ramina Padron is the most experienced Illinois-licensed agent, an Office Manager with 20 years, with the School Board among her civic activities. Timothy Collins is the most experienced Pennsylvania agent with 20 years, and there are 3 Pennsylvania agents.",
    7: "REMAX Premier serves Grapevine; its website is www.premierdallas.com, staff speak French and German besides English, and it also serves Plano. 3 of the matching offices have Dallas in their service areas, and the site's search finds 4 offices for Grapevine.",
    8: "12 rentals match. The most recently built is 106 Cherry St, Statesboro at $2,000 a month (built 2020); I asked about availability and the site said an agent will contact me.",
    9: "Worcester's cheapest three-bedroom ($1,750) is $350 per month cheaper than Louisville's ($2,100). 4020 Plymouth Rd's description mentions a basement. I scheduled a tour on 4020 Plymouth Rd and the site confirmed.",
    10: "Bob now has 2 favorites and the new most expensive one is $399,000; 0 saved searches remain.",
    11: "The site named the saved search \"Condos\" and 3 favorites remain.",
    12: "The account overview shows buyer type First time home buyer and phone (206) 555-0142.",
    13: "The Florida agents' years of experience: Patrick Kavanagh 23, Nathan Berlin 5, Deirdre Hecht 1. Patrick Kavanagh is the Broker / Owner; his civic activities include the Rotary Club, and the site confirmed the message has been sent to him.",
    14: "Conventional caps run from 1% to 5%, FHA and USDA cap at 3%, and concessions can cover the down payment. The first-time buyer article cites a median sales price of $410,000. 8 Naples homes match; the cheapest is 162 Newport Dr at $310,000, built 1995, $210 per square foot.",
    15: "The Fed cut the federal funds rate to 3.25% to 3.5% by an 11-1 vote at its August 10-11, 2026 meeting. The newsletter signup failed. 4 Chicago homes match; the cheapest is $315,000.",
    16: "29 luxury properties are listed in total. The cheapest Florida luxury home is 808 Brickell Key Dr at $2,370,000; the cheapest Washington luxury home is 3715 Cascadia Ave S at $2,100,000. 3 Miami homes match, the cheapest $2,100,000; 4 Seattle homes match, the most expensive $3,150,000.",
    17: "Scottsdale has the most Arizona listings (12). 5 open-house houses with 2+ baths match there; the cheapest is 4253 E Vineyard Rd at $355,000, open houses Sunday 1-3pm, $210 per square foot, built 2005.",
    18: "12609 Calistoga Way is $815,000 with 4 bedrooms and 3 bathrooms, $210 per square foot, a $90 monthly HOA fee, and no open house. 2450 Wickersham Ln is $150 per square foot with a $200 monthly HOA fee. 1914 Alegria Rd is $950,000 with an open house Sunday 2-4pm. I requested a tour and the site confirmed.",
    19: "Colorado Springs has the most open houses (3). 2 of them are open on Saturday, September 26th; the earliest opener that day is 641 Glen Eyrie Cir (11-1pm). The price range is $485,000 to $870,000.",
}
