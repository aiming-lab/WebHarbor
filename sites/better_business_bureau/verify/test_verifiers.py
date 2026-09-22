"""Deterministic verifier contract tests for the BETTER BUSINESS BUREAU mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (counts, anchors, sort
    orders, complaint/review anchors, scam anchors, article anchors, users),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, homepage-only navigation) MUST FAIL,
  - a tampered run package (missing run dir, corrupt trajectory, 1x1
    screenshots, mutated after-DB, truncated recording) MUST FAIL.

Task 23 special case: the seeded gym-tips article is missing its tips list
(the tracked source_catalog.json record for the article lacks the tips
paragraphs — see the review report, NEEDS-FIX item). verify_23 encodes the
POST-FIX contract (at least two upstream tips). This suite therefore asserts,
for task 23, that every adversarial case still FAILs and that an honest run
against the CURRENT seed fails specifically on the answer check (reason
"answer_tips"), never on a structural gate. Once the contributor restores the
article body, task 23's honest fixture passes unchanged and
test_23_seed_content_defect_documented must be flipped to assertIn.

The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed (DB snapshots are taken from the frozen seed DB copy).
"""
import json
import os
import random
import re
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
SEED = SITE / "instance_seed" / "better_business_bureau.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from grade import (  # noqa: E402
    T0_PROFILE, T0_YEARS, T3_PROFILE, T4_COUNT, T5_COUNT, T6_LAST_PROFILE,
    T9_TOTAL_3Y, T9_CLOSED_12M, T11_TYPE, T11_STATUS, T13_YEARS,
    T15_COUNT, T16_COUNT, T17_SCAM_ID, T18_MEDIAN, T21_COUNT,
    CAR_TENDER_ID, CAR_TENDER, XFINITY, T29_SERVICE_TOKEN,
)

BASE = "http://localhost:46059"
XFINITY_URL = BASE + XFINITY
CARTENDER_URL = BASE + CAR_TENDER
SEED_COPY = None  # per-test frozen copy of the seed DB


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


def make_png_1x1():
    """A decodable but uselessly tiny PNG (tamper fixture)."""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------- run fixture
def build_run(root, steps, final_answer, shots=None, mutate=None, terminated=True,
              corrupt=False, tiny_shots=False):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots if shots is not None else len(steps) + 1
    for i in range(frames):
        data = make_png_1x1() if tiny_shots else make_png(1000 + i)
        (root / "screenshots" / f"step_{i:03d}.png").write_bytes(data)
    shutil.copy2(SEED_COPY, root / "initial.db")
    shutil.copy2(SEED_COPY, root / "after.db")
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
    raw = json.dumps(traj, indent=1)
    if corrupt:
        raw = raw[: len(raw) // 2]
    (root / "trajectory.json").write_text(raw)
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run([sys.executable, str(VERIFY / f"verify_{number}.py"),
                           "--run_dir", str(run_dir)],
                          capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": f"non-JSON output: {proc.stdout[:200]}"}
    return proc.returncode, verdict


# ---------------------------------------------------------------- honest step builders
def nav(url, thought="navigate"):
    return (url, "navigate", {"url": url}, "fixture page text")


def inp(url, index, text, thought="input"):
    return (url, "input", {"index": index, "text": text}, f"form with {text}")


def clk(url, index, text="", thought="click"):
    return (url, "click", {"index": index, "text": text}, "fixture page text")


def login_steps(email):
    return [
        nav(BASE + "/signin"),
        inp(BASE + "/signin", 0, email),
        inp(BASE + "/signin", 1, "TestPass123!"),
        clk(BASE + "/account", 2, "Sign in"),
    ]


# ---------------------------------------------------------------- DB mutators
def mutate_t29(path):
    """Task 29's required end state: one quote request for Car Tender (brakes)."""
    with sqlite3.connect(path) as c:
        c.execute(
            "INSERT INTO quote_requests (id, business_id, user_id, name, email, phone, "
            "service_needed, message, created_at) VALUES (1, ?, NULL, 'John Reviewer', "
            "'john.reviewer@test.com', '(206) 555-0100', 'Brake inspection', "
            "'Please inspect the front brakes.', '2026-09-22 00:00:00')", (CAR_TENDER_ID,))


def mutate_readonly(path):
    """An unauthorized write any read-only task must fail on."""
    with sqlite3.connect(path) as c:
        c.execute("UPDATE businesses SET rating='F' WHERE id=?", (CAR_TENDER_ID,))


def mutate_wrong_quote(path):
    """A quote row that is NOT the requested brake inspection for Car Tender."""
    with sqlite3.connect(path) as c:
        c.execute(
            "INSERT INTO quote_requests (id, business_id, user_id, name, email, phone, "
            "service_needed, message, created_at) VALUES (1, ?, NULL, 'X', 'x@y.z', '555', "
            "'Roof repair', '', '2026-09-22 00:00:00')", (CAR_TENDER_ID,))


# ---------------------------------------------------------------- honest fixtures per task
def honest_fixture(number, root):
    """(steps, answer, mutate) replicating an honest on-site run for the task."""
    S = BASE + "/search"
    if number == 0:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "auto repair"),
                 clk(S + "?find_text=auto+repair&find_loc=Redmond%2C+WA&accredited=y", 1, "BBB Accredited"),
                 clk(BASE + T0_PROFILE, 2, "first result")]
        return steps, ("The first accredited result is A & M Auto Repair Inc, its BBB rating is A+, "
                       f"and it has {T0_YEARS} years in business."), None
    if number == 1:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "Precision Tune"),
                 clk(S + "?find_text=Precision+Tune&find_loc=Seattle%2C+WA", 1, "Search")]
        return steps, ("Two businesses named Precision Tune Auto Care appear: the Seattle location "
                       "(8401 Aurora Ave N) shows BBB rating NR, and the University Place location "
                       "(4828 Bridgeport Way W) shows BBB rating B-."), None
    if number == 2:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "hotels"),
                 clk(S + "?find_text=hotels&find_loc=New+York%2C+NY&ratings=F", 1, "F")]
        return steps, ("The F-rated hotels shown are: Crowne Plaza/Marriot, Eastside Marriott, "
                       "J W Marriott Hotel, New York Marriott East Side, New York Marriott Marquis, "
                       "and Residence Inn Marriott Times Square."), None
    if number == 3:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "State Farm Insurance"),
                 clk(S + "?find_text=State+Farm+Insurance&find_loc=Chicago%2C+IL", 1, "Search"),
                 clk(BASE + T3_PROFILE, 2, "State Farm Insurance")]
        return steps, "State Farm Insurance has BBB rating F and its city is Chicago, IL.", None
    if number == 4:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "internet providers"),
                 clk(S + "?find_text=internet+providers&find_loc=Chicago%2C+IL", 1, "Search")]
        return steps, (f"{T4_COUNT} results are shown; the first result is Xfinity (Comcast) "
                       "with BBB rating A+."), None
    if number == 5:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "dentist"),
                 clk(S + "?find_text=dentist&find_loc=Seattle%2C+WA", 1, "Search")]
        return steps, (f"{T5_COUNT} results are shown and the first BBB-accredited dental business "
                       "is Beacon Hill Dental Associates LLC."), None
    if number == 6:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "hotels"),
                 clk(S + "?find_text=hotels&find_loc=New+York%2C+NY&sort=rating", 1, "Rating")]
        return steps, ("The lowest-rated business on the first page is Residence Inn Marriott "
                       "Times Square with BBB rating F."), None
    if number in (7, 8, 12):
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "Xfinity"),
                 clk(S + "?find_text=Xfinity&find_loc=Chicago%2C+IL", 1, "Search"),
                 clk(XFINITY_URL, 2, "Xfinity (Comcast)")]
        if number == 7:
            return steps, ("In Business Details: BBB File Opened 1/16/1990, Business Started "
                           "7/28/1963, Type of Entity Corporation."), None
        if number == 8:
            return steps, ("Under Business Management, Mr. Brian Roberts is listed as "
                           "Chairperson/CEO."), None
        return steps, ("Xfinity accepts credit card, debit card, and bank account payments."), None
    if number in (9, 11):
        steps = [nav(XFINITY_URL), clk(XFINITY_URL + "/complaints", 1, "COMPLAINTS")]
        if number == 9:
            return steps, (f"Total complaints in the last 3 years: {T9_TOTAL_3Y:,}; "
                           f"complaints closed in the last 12 months: {T9_CLOSED_12M:,}."), None
        return steps, (f"The complaint about being charged $109.00 is of type {T11_TYPE}, "
                       f"its status is {T11_STATUS}, and the initial complaint was filed on 03/04/2026."), None
    if number == 10:
        steps = [nav(XFINITY_URL), clk(XFINITY_URL + "/customer-reviews", 1, "REVIEWS")]
        return steps, ("The review that warns other consumers about a deceptive billing practice "
                       "was written by Courtland P, is dated 04/22/2025, and gives 1 of 5 stars."), None
    if number in (13, 14):
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "auto repair"),
                 clk(S + "?find_text=auto+repair&find_loc=Redmond%2C+WA", 1, "Search"),
                 clk(CARTENDER_URL, 2, "Car Tender")]
        if number == 13:
            return steps, (f"Car Tender's Local BBB is BBB Great West + Pacific, its BBB File Opened "
                           f"date is 2/1/1999, and it has {T13_YEARS} years in business."), None
        return steps, ("Car Tender's phone number is (206) 324-0345 and it offers quotes."), None
    if number == 15:
        steps = [nav(BASE + "/scamtracker"),
                 clk(BASE + "/scamtracker/lookupscam?scam_type=Charity", 1, "Look Up a Scam")]
        return steps, (f"{T15_COUNT} search results are shown; the report involving the business "
                       "Blue Heart Advocacy is located in Miami, FL and was reported on 2026-09-19."), None
    if number == 16:
        steps = [nav(BASE + "/scamtracker"),
                 clk(BASE + "/scamtracker/lookupscam?scam_type=Charity&state=WA", 1, "WA")]
        return steps, (f"{T16_COUNT} reports involve the scam business name Rise Up Youth Foundation, "
                       "with losses of $700, $1,485, $800, $1,000, $1,000, and $2,000."), None
    if number == 17:
        steps = [nav(BASE + "/scamtracker"),
                 clk(BASE + "/scamtracker/lookupscam?q=1388290", 1, "Look Up a Scam"),
                 clk(BASE + f"/scamtracker/lookupscam/{T17_SCAM_ID}", 2, "1388290")]
        return steps, ("Scam report 1388290 is a Charity scam, reported from Seattle, WA, "
                       "with a dollar amount lost of $700."), None
    if number == 18:
        steps = [nav(BASE + "/scamtracker"), clk(BASE + "/scamtracker/dashboard", 1, "Heatmap")]
        return steps, (f"The state with the most scam reports is California (CA), the median loss is "
                       f"${T18_MEDIAN}, and 47.6% of reports lost money."), None
    if number == 19:
        steps = [nav(BASE + "/scamtracker"),
                 clk(BASE + "/scamtracker/lookupscam?q=gift+card", 1, "Look Up a Scam")]
        return steps, ("The results include at least three different scam types: Charity, Romance, "
                       "and Tech Support (Utility also appears)."), None
    if number == 20:
        steps = [nav(BASE + "/scamtracker"), clk(BASE + "/scamtracker/reportscam", 1, "Report a Scam")]
        return steps, ("The form asks a consumer to provide: the scam type, what happened, their city, "
                       "their state, their ZIP code, the scammer's phone, the scammer's email, the "
                       "scammer's website, the business named in the scam, and the dollar amount lost."), None
    if number == 21:
        steps = [nav(BASE + "/scamtracker"),
                 clk(BASE + "/scamtracker/lookupscam?scam_type=CryptoCurrency", 1, "Look Up a Scam")]
        return steps, (f"{T21_COUNT} search results are shown; the newest report is located in "
                       "Palm Desert, CA and was reported on 2026-09-18."), None
    if number == 22:
        steps = [nav(BASE + "/us/news"), clk(BASE + "/us/news/bbb-tip-don-t-get-scammed-out-of-a-gift-card", 1, "gift card")]
        return steps, ("BBB says to physically check for tampering with the stickers covering barcodes: "
                       "run your finger over the back to check whether a sticker has been applied on top "
                       "of the barcode, because scammers add fraudulent barcode stickers over the card's "
                       "real barcode so the money paid loads onto the scammer's account."), None
    if number == 23:
        steps = [nav(BASE + "/us/news"), clk(BASE + "/us/news/bbb-tip-need-to-get-in-shape-bbb-has-tips-for-joining-a-gym", 1, "gym")]
        return steps, ("Before signing a gym membership contract, BBB says to determine your fitness "
                       "goals in advance, know your budget and check for hidden costs such as enrollment "
                       "fees or cancellation fees, and take a tour of the gym in person."), None
    if number == 24:
        steps = [nav(BASE + "/us/news"),
                 clk(BASE + "/us/news/celebrating-integrity-international-torch-awards-for-ethics-announce-2026-winners", 1, "Torch")]
        return steps, ("The International Association of Better Business Bureaus (IABBB) announced the "
                       "winners; the International Torch Awards for Ethics celebrate businesses that "
                       "maintain outstanding dedication to upholding ethical business practices and "
                       "promoting trust in the marketplace."), None
    if number == 25:
        steps = [nav(BASE + "/us/news"),
                 clk(BASE + "/us/news/bbb-scam-alert-use-caution-when-searching-for-weight-loss-products-online", 1, "weight loss")]
        return steps, ("The scam involves deep-fake videos of celebrities such as Oprah Winfrey and "
                       "alleged physicians endorsing a weight loss product called LipoMax, marketed as "
                       "the pink salt trick; BBB Scam Tracker received over 170 reports over the course "
                       "of two months."), None
    if number == 26:
        steps = login_steps("carol.d@test.com") + [nav(BASE + "/account")]
        return steps, ("The business in Carol's favorites is Accurate Auto Body Inc, located in "
                       "Redmond, WA, with BBB rating A+."), None
    if number == 27:
        steps = login_steps("carol.d@test.com") + [nav(BASE + "/account")]
        return steps, ("Carol's review was written about Accurate Auto Body Inc, it is rated 4 of 5 "
                       "stars, and its date is 01/20/2026."), None
    if number == 28:
        steps = login_steps("alice.j@test.com") + [nav(BASE + "/account")]
        return steps, ("Alice's scam report is a Phishing report describing a text message claiming "
                       "that a package delivery needed an extra payment, with a tracking link that led "
                       "to a fake courier site asking for card details."), None
    if number == 29:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "auto repair"),
                 clk(S + "?find_text=auto+repair&find_loc=Redmond%2C+WA", 1, "Search"),
                 clk(CARTENDER_URL, 2, "Car Tender"),
                 clk(BASE + f"/get-a-quote/{CAR_TENDER_ID}", 3, "Get a Quote"),
                 inp(BASE + f"/get-a-quote/{CAR_TENDER_ID}", 0, "John Reviewer"),
                 clk(BASE + f"/get-a-quote/{CAR_TENDER_ID}", 4, "Send Request")]
        return steps, ("After submitting the quote request for a brake inspection, the confirmation "
                       "message said: 'Your quote request has been sent to the business.'"), mutate_t29
    raise ValueError(number)


# ---------------------------------------------------------------- the tests
class BBBVerifierContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global SEED_COPY
        cls.maxDiff = None
        SEED_COPY = Path(tempfile.mkdtemp(prefix="wh-bbb-seed-")) / "seed.db"
        shutil.copy2(SEED, SEED_COPY)
        cls.seed_copy = SEED_COPY
        cls.tmp = Path(tempfile.mkdtemp(prefix="wh-bbb-tests-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        shutil.rmtree(SEED_COPY.parent, ignore_errors=True)

    def fresh(self, name):
        d = self.tmp / name
        if d.exists():
            shutil.rmtree(d)
        return d

    # ---- per-task contract matrix
    def check_task(self, number):
        steps, answer, mutate = honest_fixture(number, None)
        # 1. honest run passes
        root = build_run(self.fresh(f"t{number}_honest"), steps, answer, mutate=mutate)
        code, verdict = run_verifier(number, root)
        self.assertEqual(code, 0, f"task {number} honest run must PASS: {json.dumps(verdict)[:800]}")
        self.assertTrue(verdict["pass"], f"task {number} honest verdict: {verdict['reason']}")
        # 2. no-op run fails
        noop = build_run(self.fresh(f"t{number}_noop"), [nav(BASE + "/")], "")
        code, verdict = run_verifier(number, noop)
        self.assertNotEqual(code, 0, f"task {number} no-op must FAIL")
        self.assertFalse(verdict["pass"])
        # 3. wrong answer fails
        wrong = build_run(self.fresh(f"t{number}_wrong"), steps,
                          "A wrong answer with no basis in the site.", mutate=mutate)
        code, verdict = run_verifier(number, wrong)
        self.assertNotEqual(code, 0, f"task {number} wrong answer must FAIL")
        self.assertFalse(verdict["pass"])
        # 4. shortcut (correct answer, homepage-only navigation) fails
        shortcut = build_run(self.fresh(f"t{number}_shortcut"), [nav(BASE + "/")], answer, mutate=mutate)
        code, verdict = run_verifier(number, shortcut)
        self.assertNotEqual(code, 0, f"task {number} shortcut must FAIL")
        self.assertFalse(verdict["pass"])
        # 5a. corrupt trajectory fails closed
        corrupt = build_run(self.fresh(f"t{number}_corrupt"), steps, answer, mutate=mutate, corrupt=True)
        code, verdict = run_verifier(number, corrupt)
        self.assertNotEqual(code, 0, f"task {number} corrupt trajectory must FAIL")
        self.assertFalse(verdict["pass"])
        # 5b. tiny screenshots fail closed
        tiny = build_run(self.fresh(f"t{number}_tiny"), steps, answer, mutate=mutate, tiny_shots=True)
        code, verdict = run_verifier(number, tiny)
        self.assertNotEqual(code, 0, f"task {number} tiny screenshots must FAIL")
        self.assertFalse(verdict["pass"])
        # 5c. missing run dir fails closed
        code, verdict = run_verifier(number, self.fresh(f"t{number}_missing"))
        self.assertNotEqual(code, 0, f"task {number} missing run dir must FAIL")
        self.assertFalse(verdict["pass"])
        # 5d. mutated after-DB fails (read-only: any write; stateful: wrong final state)
        if mutate is None:
            tampered = build_run(self.fresh(f"t{number}_dbtamper"), steps, answer, mutate=mutate_readonly)
        else:
            tampered = build_run(self.fresh(f"t{number}_dbtamper"), steps, answer)  # missing the required mutation
        code, verdict = run_verifier(number, tampered)
        self.assertNotEqual(code, 0, f"task {number} tampered DB must FAIL")
        self.assertFalse(verdict["pass"])
        # 5e. truncated run (no done step / not terminated) fails
        truncated = build_run(self.fresh(f"t{number}_trunc"), steps, answer, mutate=mutate, terminated=False)
        code, verdict = run_verifier(number, truncated)
        self.assertNotEqual(code, 0, f"task {number} truncated run must FAIL")
        self.assertFalse(verdict["pass"])

    def test_00_contract(self): self.check_task(0)
    def test_01_contract(self): self.check_task(1)
    def test_02_contract(self): self.check_task(2)
    def test_03_contract(self): self.check_task(3)
    def test_04_contract(self): self.check_task(4)
    def test_05_contract(self): self.check_task(5)
    def test_06_contract(self): self.check_task(6)
    def test_07_contract(self): self.check_task(7)
    def test_08_contract(self): self.check_task(8)
    def test_09_contract(self): self.check_task(9)
    def test_10_contract(self): self.check_task(10)
    def test_11_contract(self): self.check_task(11)
    def test_12_contract(self): self.check_task(12)
    def test_13_contract(self): self.check_task(13)
    def test_14_contract(self): self.check_task(14)
    def test_15_contract(self): self.check_task(15)
    def test_16_contract(self): self.check_task(16)
    def test_17_contract(self): self.check_task(17)
    def test_18_contract(self): self.check_task(18)
    def test_19_contract(self): self.check_task(19)
    def test_20_contract(self): self.check_task(20)
    def test_21_contract(self): self.check_task(21)
    def test_22_contract(self): self.check_task(22)
    def test_23_contract(self): self.check_task(23)
    def test_24_contract(self): self.check_task(24)
    def test_25_contract(self): self.check_task(25)
    def test_26_contract(self): self.check_task(26)
    def test_27_contract(self): self.check_task(27)
    def test_28_contract(self): self.check_task(28)
    def test_29_contract(self): self.check_task(29)

    # ---- task 23: documented seed content defect (gym tips list missing)
    def test_23_seed_content_fixed(self):
        """F1 FIXED: the seeded gym-tips article now carries its tips list.

        The contributor re-scraped the article bodies with an extractor that
        captures list-based tip blocks (li + p + h3 with junk filters). The
        seeded article body must now contain the upstream tips so an honest
        agent can report them (flipped from assertNotIn per the review
        NEEDS-FIX instruction once the seed fix landed).
        """
        gym = self.db_rows("SELECT body FROM articles WHERE slug=?",
                           ("bbb-tip-need-to-get-in-shape-bbb-has-tips-for-joining-a-gym",))[0]["body"]
        for tip_marker in ("Know your budget", "Determine your fitness goals",
                           "Figure out your priorities", "Take a tour"):
            self.assertIn(tip_marker, gym,
                          f"gym article must contain {tip_marker!r} after the seed fix")

    # ---- ground-truth sanity against the frozen seed DB
    def db_rows(self, sql, args=()):
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()

    def test_ground_truth_search_anchors(self):
        biz = self.db_rows("SELECT * FROM businesses")
        self.assertEqual(len(biz), 349)
        by_id = {b["id"]: b for b in biz}
        self.assertEqual(by_id[1000032981]["name"], "A & M Auto Repair Inc")
        self.assertEqual((by_id[1000032981]["rating"], by_id[1000032981]["accredited"], by_id[1000032981]["years_in_business"]), ("A+", 1, 13))
        self.assertEqual(by_id[26851]["name"], "State Farm Insurance")
        self.assertEqual((by_id[26851]["rating"], by_id[26851]["city"]), ("F", "Chicago"))
        self.assertEqual(by_id[27568]["name"], "Xfinity (Comcast)")
        self.assertEqual((by_id[27568]["file_opened"], by_id[27568]["started"], by_id[27568]["entity_type"]), ("1/16/1990", "7/28/1963", "Corporation"))
        self.assertIn("Brian Roberts, Chairperson/CEO", by_id[27568]["management"])
        self.assertEqual(by_id[27568]["payment_methods"], "Credit card, Debit card, Bank account")
        self.assertEqual((by_id[27568]["complaints_total"], by_id[27568]["complaints_closed_12m"]), (26666, 8188))
        self.assertEqual(by_id[7042420]["name"], "Car Tender")
        self.assertEqual((by_id[7042420]["file_opened"], by_id[7042420]["years_in_business"], by_id[7042420]["phone"]), ("2/1/1999", 27, "(206) 324-0345"))
        self.assertEqual(by_id[7042420]["offers_quotes"], 1)
        # T2: F-rated hotels near New York
        f_hotels = [b for b in biz if b["rating"] == "F" and
                    re.search(r"marriott|crowne|hotel", (b["name"] or ""), re.I) and
                    b["city"] and "new york" in b["city"].strip().lower()]
        names = {b["name"] for b in f_hotels}
        self.assertIn("Residence Inn Marriott Times Square", names)
        self.assertIn("Eastside Marriott", names)
        # T4: internet providers near Chicago — replica of the app's token-overlap
        # search (name/category/about/categories/products) scoped to IL.
        def hay(b):
            parts = [b["name"] or "", b["primary_category"] or "", b["about"] or "",
                     " ".join(json.loads(b["categories"] or "[]")),
                     " ".join(json.loads(b["products_services"] or "[]"))]
            return " ".join(parts).lower()
        def score(b):
            return sum(1 for t in ("internet", "providers") if t in hay(b))
        il_ip = [b for b in biz if (b["state"] == "IL")
                 and any(t in hay(b) for t in ("internet", "providers"))]
        il_ip.sort(key=lambda b: (-int(b["accredited"]), -score(b), b["name"].lower()))
        self.assertEqual(len(il_ip), 3)
        self.assertEqual(il_ip[0]["name"], "Xfinity (Comcast)")
        self.assertEqual(il_ip[0]["rating"], "A+")
        # T5: accredited Seattle dentists
        dent = [b for b in biz if b["city"] == "Seattle" and b["accredited"] == 1 and
                ("dental" in (b["name"] or "").lower() or "dentist" in (b["primary_category"] or "").lower())]
        self.assertTrue(any(d["name"] == "Beacon Hill Dental Associates LLC" for d in dent))

    def test_ground_truth_scam_anchors(self):
        scams = self.db_rows("SELECT * FROM scam_reports")
        self.assertEqual(len(scams), 626)
        charity = [s for s in scams if s["scam_type"] == "Charity"]
        crypto = [s for s in scams if s["scam_type"] == "CryptoCurrency"]
        self.assertEqual(len(charity), 37)
        self.assertEqual(len(crypto), 39)
        report = {s["scam_id"]: s for s in scams}[T17_SCAM_ID]
        self.assertEqual((report["scam_type"], report["target_city"], report["target_state"], report["dollar_value"]),
                         ("Charity", "Seattle", "WA", 700))
        rise_up = [s for s in charity if "Rise Up Youth" in (s["scammer_business_name"] or "") and s["target_state"] == "WA"]
        self.assertEqual(len(rise_up), 6)
        self.assertEqual(sorted(s["dollar_value"] for s in rise_up), sorted([700, 1485, 800, 1000, 1000, 2000]))
        blue_heart = [s for s in charity if "Blue Heart" in (s["scammer_business_name"] or "")]
        self.assertEqual(len(blue_heart), 1)
        self.assertEqual((blue_heart[0]["target_city"], blue_heart[0]["target_state"], blue_heart[0]["date_reported"]),
                         ("Miami", "FL", "2026-09-19"))
        # T19: gift card keyword matches 7 reports across 4 scam types
        gift = [s for s in scams if "gift card" in (s["description"] or "").lower()]
        self.assertEqual(len(gift), 7)
        self.assertEqual({s["scam_type"] for s in gift}, {"Charity", "Romance", "Tech Support", "Utility"})
        # T21: newest CryptoCurrency report
        newest = max(crypto, key=lambda s: (s["date_reported"], s["scam_id"]))
        self.assertEqual((newest["target_city"], newest["target_state"], newest["date_reported"]),
                         ("Palm Desert", "CA", "2026-09-18"))
        # T18: dashboard figures (12m window covers the whole seed)
        by_state = {}
        for s in scams:
            by_state[s["target_state"]] = by_state.get(s["target_state"], 0) + 1
        top_state = max(by_state, key=lambda st: by_state[st])
        self.assertEqual((top_state, by_state[top_state]), ("CA", 58))
        losses = sorted(s["dollar_value"] for s in scams if s["dollar_value"] > 0)
        self.assertEqual(losses[len(losses) // 2], 500)
        self.assertAlmostEqual(100.0 * len(losses) / len(scams), 47.6, places=1)

    def test_ground_truth_complaint_review_article_anchors(self):
        complaints = self.db_rows("SELECT * FROM complaints")
        self.assertEqual(len(complaints), 536)
        xfinity_c = [c for c in complaints if c["business_id"] == 27568]
        self.assertEqual(len(xfinity_c), 1)
        c109 = xfinity_c[0]
        self.assertIn("$109.00", c109["text"])
        self.assertEqual((c109["complaint_type"], c109["status"], c109["complaint_date"]),
                         ("Product Issues", "Resolved", "03/04/2026"))
        reviews = self.db_rows("SELECT * FROM reviews")
        self.assertEqual(len(reviews), 577)
        warn = [r for r in reviews if r["business_id"] == 27568 and "warn" in (r["text"] or "").lower()]
        self.assertEqual(len(warn), 1)
        self.assertEqual((warn[0]["author_name"], warn[0]["review_date"], warn[0]["rating"]),
                         ("Courtland P", "04/22/2025", 1))
        articles = {a["slug"]: a for a in self.db_rows("SELECT * FROM articles")}
        self.assertEqual(len(articles), 40)
        gift = articles["bbb-tip-don-t-get-scammed-out-of-a-gift-card"]
        self.assertIn("run your finger over the back", gift["body"])
        gym = articles["bbb-tip-need-to-get-in-shape-bbb-has-tips-for-joining-a-gym"]
        self.assertIn("Know your budget", gym["body"])  # F1 fixed: tips present after the re-scrape (see test_23)
        torch = articles["celebrating-integrity-international-torch-awards-for-ethics-announce-2026-winners"]
        self.assertIn("International Association of Better Business Bureaus (IABBB)", torch["body"])
        wl = articles["bbb-scam-alert-use-caution-when-searching-for-weight-loss-products-online"]
        self.assertIn("LipoMax", wl["body"])
        self.assertIn("over 170 reports", wl["body"])

    def test_ground_truth_account_anchors(self):
        users = {u["email"]: u for u in self.db_rows("SELECT * FROM users")}
        self.assertEqual(len(users), 4)
        carol = users["carol.d@test.com"]
        alice = users["alice.j@test.com"]
        favs = self.db_rows("SELECT * FROM favorites")
        self.assertEqual(len(favs), 1)
        fav_biz = {b["id"]: b for b in self.db_rows("SELECT * FROM businesses")}[favs[0]["business_id"]]
        self.assertEqual((fav_biz["name"], fav_biz["city"], fav_biz["state"], fav_biz["rating"]),
                         ("Accurate Auto Body Inc", "Redmond", "WA", "A+"))
        carol_reviews = [r for r in self.db_rows("SELECT * FROM reviews") if r["user_id"] == carol["id"]]
        self.assertEqual(len(carol_reviews), 1)
        self.assertEqual((carol_reviews[0]["rating"], carol_reviews[0]["review_date"]), (4, "01/20/2026"))
        alice_subs = [s for s in self.db_rows("SELECT * FROM scam_submissions") if s["user_id"] == alice["id"]]
        self.assertEqual(len(alice_subs), 1)
        self.assertEqual(alice_subs[0]["scam_type"], "Phishing")
        self.assertEqual(self.db_rows("SELECT COUNT(*) c FROM quote_requests")[0]["c"], 0)

    # ---- answers predicates
    def test_answers_predicates(self):
        self.assertTrue(answers.payment_methods("It accepts credit card, debit card, and bank account payments."))
        self.assertFalse(answers.payment_methods("It accepts cash only."))
        self.assertFalse(answers.payment_methods("It accepts credit card and debit card."))
        self.assertTrue(answers.complaint_summary("26,666 total complaints and 8,188 closed in the last 12 months."))
        self.assertFalse(answers.complaint_summary("1,000 total and 500 closed."))
        self.assertTrue(answers.dashboard_figures("California has the most reports; median loss $500; 47.6% lost money."))
        self.assertFalse(answers.dashboard_figures("Texas has the most reports; median loss $300; 50% lost money."))
        self.assertTrue(answers.rise_up_amounts("Losses: $700, $1,485, $800, $1,000, $1,000 and $2,000."))
        self.assertFalse(answers.rise_up_amounts("Losses: $700 and $1,485 only."))
        self.assertTrue(answers.gift_card_check("Run your finger over the back to check whether a sticker has been "
                                                "applied on top of the barcode; scammers' barcode stickers route the "
                                                "payment to their own account."))
        self.assertFalse(answers.gift_card_check("Buy the card online from the merchant's real website."))
        self.assertTrue(answers.gift_card_types("The results include Charity, Romance, and Tech Support scams.", 3))
        self.assertFalse(answers.gift_card_types("Only Charity scams appear.", 3))
        self.assertTrue(answers.report_form_fields("It asks for scam type, what happened, city, state, ZIP, phone, "
                                                   "email, website, business name and dollar amount.", 6))
        self.assertFalse(answers.report_form_fields("It asks for your name and your address.", 6))
        self.assertTrue(answers.torch_awards("IABBB announced the winners; the awards celebrate ethical business "
                                             "practices and trust in the marketplace."))
        self.assertFalse(answers.torch_awards("The BBB of Chicago announced the winners of the holiday contest."))
        self.assertTrue(answers.weight_loss_scam("Deep-fake videos of celebrities endorsing LipoMax; over 170 reports "
                                                 "in two months."))
        self.assertFalse(answers.weight_loss_scam("Fake invoices by email; 40 reports."))
        self.assertTrue(answers.warn_review_rating("1 of 5 stars"))
        self.assertFalse(answers.warn_review_rating("5 of 5 stars"))
        self.assertTrue(answers.precision_tune_ratings("Seattle shows NR and University Place shows B-."))
        self.assertFalse(answers.precision_tune_ratings("Seattle shows A+ and Bellevue shows A."))
        self.assertTrue(answers.quote_confirmation("Your quote request has been sent to the business."))
        self.assertFalse(answers.quote_confirmation("No confirmation was shown."))
        self.assertTrue(answers.gym_tips("Determine your fitness goals and know your budget before signing.", 2))
        self.assertFalse(answers.gym_tips("Join a gym today to get in shape.", 2))

    # ---- verifier 29 state-specific adversarial case: right flow, wrong service
    def test_29_wrong_service_fails(self):
        steps, answer, _ = honest_fixture(29, None)
        root = build_run(self.fresh("t29_wrongsvc"), steps, answer, mutate=mutate_wrong_quote)
        code, verdict = run_verifier(29, root)
        self.assertNotEqual(code, 0, "wrong-service quote row must FAIL")
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
