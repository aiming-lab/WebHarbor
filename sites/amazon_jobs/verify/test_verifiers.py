"""Deterministic verifier contract tests for the AMAZON JOBS mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (counts, facet pools,
    sort orders, job anchors, seed users/applications/alerts),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, homepage-only navigation) MUST FAIL,
  - a tampered run package (missing run dir, corrupt trajectory, 1x1
    screenshots, mutated after-DB) MUST FAIL.
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
SEED = SITE / "instance_seed" / "amazon_jobs.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from grade import (  # noqa: E402
    T0_SEATTLE_ENGINEER, T1_PART_TIME, T2_FIRST_RECENT, T3_TOKYO,
    T4_DEVICES, T5_JOB, T5_COMPANY, T6_JOB, T6_COMPANY, T7_OPS_7Y,
    T8_JOB, T9_JOB, T10_JOB_A, T10_JOB_B, T11_JOB,
    T12_SWDEV_FIRST_SECTION, T13_VOICES, T13_FIRST_NAME, T14_MARKETING_OPEN,
    T15_US_LOCATIONS, T16_SEATTLE_HERO, T16_MOST_RECENT, T17_AIS,
    T19_TIME_AWAY, T20_STEPS, T20_FIRST_STEP, T22_AI_RUNTIME_STATUS,
    T23_WITHDRAW_APP_ID, T24_ALERT_QUERY, T24_MATCH, T25_HEADLINE, T25_CITY,
    T27_JOB, T27_JOB_PK, T28_ALERT_ID, T29_FULFILLMENT_LT1,
)

BASE = "http://localhost:40059"
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
def build_run(root, steps, final_answer, shots=None, mutate=None, terminated=True, corrupt=False, tiny_shots=False):
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
        nav(BASE + "/login"),
        inp(BASE + "/login", 0, email),
        inp(BASE + "/login", 1, "TestPass123!"),
        clk(BASE + "/applicant/dashboard/applications", 2, "Continue"),
    ]


# ---------------------------------------------------------------- DB mutators
def mutate_t23(path):
    with sqlite3.connect(path) as c:
        c.execute("UPDATE applications SET status='Withdrawn' WHERE id=?", (T23_WITHDRAW_APP_ID,))


def mutate_t24(path):
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO job_alerts (id, user_id, query_text, location_text, frequency, active, created_at) "
                  "VALUES (7, 3, ?, '', 'Monthly', 1, '2026-09-22 00:00:00')", (T24_ALERT_QUERY,))


def mutate_t25(path):
    with sqlite3.connect(path) as c:
        c.execute("UPDATE users SET headline=? WHERE id=4", (T25_HEADLINE,))


def mutate_t26(path):
    with sqlite3.connect(path) as c:
        c.execute("UPDATE users SET notify_recommendations=0 WHERE id=1")


def mutate_t27(path):
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO applications (id, user_id, job_id, status, submitted_at, updated_at) "
                  "VALUES (13, 4, ?, 'Submitted', '2026-09-22 00:00:00', '2026-09-22 00:00:00')", (T27_JOB_PK,))


def mutate_t28(path):
    with sqlite3.connect(path) as c:
        c.execute("DELETE FROM job_alerts WHERE id=?", (T28_ALERT_ID,))


def mutate_readonly(path):
    """An unauthorized write any read-only task must fail on."""
    with sqlite3.connect(path) as c:
        c.execute("UPDATE applications SET status='Offer' WHERE id=1")


# ---------------------------------------------------------------- honest fixtures per task
def honest_fixture(number, root):
    """(steps, answer, mutate) replicating an honest on-site run for the task."""
    S = BASE + "/search"
    if number == 0:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "data engineer"),
                 clk(S + "?base_query=data+engineer&loc_keyword=Seattle", 1, "search")]
        return steps, f"There are {T0_SEATTLE_ENGINEER} results listed for data engineer jobs in Seattle.", None
    if number == 1:
        steps = [nav(BASE + "/"), nav(S),
                 clk(S + "?job_type=Part+Time", 2, "Part Time")]
        return steps, f"There are {T1_PART_TIME} Part Time jobs currently listed.", None
    if number == 2:
        steps = [nav(BASE + "/"), nav(S),
                 clk(S + "?category=hardware-development", 2, "Hardware Development"),
                 clk(S + "?category=hardware-development&sort_by=recent", 3, "Most recent")]
        return steps, f"The first job listed is '{T2_FIRST_RECENT}'.", None
    if number == 3:
        steps = [nav(BASE + "/"), nav(S), clk(S + "?city=Tokyo", 2, "Tokyo")]
        return steps, f"There are {T3_TOKYO} open jobs listed for Tokyo.", None
    if number == 4:
        steps = [nav(BASE + "/"), nav(S)]
        return steps, f"{T4_DEVICES} has more open jobs: 71 vs 31 for Amazon Ads.", None
    if number == 5:
        steps = [nav(BASE + "/"), nav(S),
                 clk(S + "?category=data-science", 2, "Data Science"),
                 clk(S + "?category=data-science&country=India", 2, "India"),
                 clk(S + "?category=data-science&country=India&sort_by=recent", 3, "Most recent"),
                 clk(BASE + f"/jobs/{T5_JOB}/data-scientist-scot-supply-chain-optimization-technologies-row-tech", 4, "first result")]
        return steps, f"The company name shown in the 'Job ID' line is {T5_COMPANY}.", None
    if number == 6:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "intern"),
                 clk(S + "?base_query=intern&loc_keyword=India", 1, "search"),
                 clk(S + "?base_query=intern&loc_keyword=India&sort_by=recent", 3, "Most recent"),
                 clk(BASE + f"/jobs/{T6_JOB}/financial-analyst-intern-accounting", 4, "first result")]
        return (steps,
                f"The most recently posted internship in India is 'Financial Analyst Intern, Accounting' "
                f"(Job ID {T6_JOB}), and the company name in the 'Job ID' line is {T6_COMPANY}.", None)
    if number == 7:
        steps = [nav(BASE + "/"), nav(S),
                 clk(S + "?business_category=amazon-operations", 2, "Amazon Operations"),
                 clk(S + "?business_category=amazon-operations&experience=7%2B+years", 2, "7+ years")]
        return steps, f"{T7_OPS_7Y} jobs on the Amazon Operations team require 7+ years of industry experience.", None
    if number == 8:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "Dir NAMER SA"),
                 clk(S + "?base_query=Dir+NAMER+SA", 1, "search"),
                 clk(BASE + f"/jobs/{T8_JOB}/dir-namer-sa-isv-data-and-ai-ags-namer-tech", 4, "first result")]
        return steps, "The company name shown in the 'Job ID' line is Amazon Web Services, Inc.", None
    if number == 9:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "Senior UX Designer, Fashion and Fitness"),
                 clk(S + "?base_query=Senior+UX+Designer%2C+Fashion+and+Fitness", 1, "search"),
                 clk(BASE + f"/jobs/{T9_JOB}/senior-ux-designer-fashion-and-fitness-subs", 4, "first result")]
        return steps, "The job asks for experience working with scalable design systems.", None
    if number == 10:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "UX Designer"),
                 clk(S + "?base_query=UX+Designer", 1, "search"),
                 clk(S + "?base_query=UX+Designer&city=New+York", 2, "New York"),
                 clk(BASE + f"/jobs/{T10_JOB_B}/ux-designer-elevated-shopping-experience", 4, "Elevated"),
                 clk(BASE + f"/jobs/{T10_JOB_A}/senior-ux-designer-fashion-and-fitness-subs", 5, "Fashion and Fitness")]
        return (steps,
                "The 'UX Designer, Elevated Shopping Experience' job mentions a degree requirement: "
                "a Bachelor's degree or above in design or human-computer interaction (HCI).", None)
    if number == 11:
        steps = [nav(BASE + "/"), inp(BASE + "/", 0, "Area Manager, Print on Demand"),
                 clk(S + "?base_query=Area+Manager%2C+Print+on+Demand", 1, "search"),
                 clk(BASE + f"/jobs/{T11_JOB}/area-manager-print-on-demand", 4, "first result")]
        return steps, "In the Job details sidebar the location listed is AUS, NSW, Sydney.", None
    if number == 12:
        steps = [nav(BASE + "/job_categories"),
                 clk(BASE + "/job_categories/software-development", 2, "Software Development")]
        return steps, f"The heading of the first content section below the hero is '{T12_SWDEV_FIRST_SECTION}'.", None
    if number == 13:
        steps = [nav(BASE + "/job_categories"),
                 clk(BASE + "/job_categories/software-development", 2, "Software Development")]
        return (steps, f"{T13_VOICES} Amazonians are quoted in the Voices of Amazonians section, "
                f"and the first one is {T13_FIRST_NAME}.", None)
    if number == 14:
        steps = [nav(BASE + "/job_categories"),
                 clk(BASE + "/job_categories/marketing", 2, "Marketing")]
        return steps, f"The page says there are {T14_MARKETING_OPEN} open Marketing jobs available right now.", None
    if number == 15:
        steps = [nav(BASE + "/locations")]
        return steps, f"There are {T15_US_LOCATIONS} Amazon locations listed under the United States region.", None
    if number == 16:
        steps = [nav(BASE + "/locations"),
                 clk(BASE + "/locations/united-states/washington/seattle", 2, "Seattle, Washington"),
                 clk(BASE + "/locations/united-states/washington/seattle?sort_by=recent", 3, "Most recent")]
        return (steps, f"The hero shows {T16_SEATTLE_HERO} open jobs, and the most recently posted job "
                f"in the results is '{T16_MOST_RECENT}'.", None)
    if number == 17:
        steps = [nav(BASE + "/business_categories"),
                 clk(BASE + "/business_categories/amazon-web-services", 2, "Amazon Web Services")]
        return (steps, f"The 'Make the cloud do more' section says the {T17_AIS} team handles the design, "
                f"planning, delivery, and operation of all AWS global infrastructure.", None)
    if number == 18:
        steps = [nav(BASE + "/faq"),
                 clk(BASE + "/faq", 2, "Where can I find open roles?")]
        return (steps, "Amazon encourages you to use this website, and you can filter your search by "
                "locations, business categories, job categories, or keywords.", None)
    if number == 19:
        steps = [nav(BASE + "/benefits/global")]
        return steps, f"The heading of the section about taking time away from work is '{T19_TIME_AWAY}'.", None
    if number == 20:
        steps = [nav(BASE + "/how-we-hire")]
        return (steps, f"The page shows {T20_STEPS} steps of the interview process, "
                f"and the first step is called '{T20_FIRST_STEP}'.", None)
    if number == 21:
        return [nav(BASE + "/")], ("The homepage employee story is about Xiaole: Engineer | Amazon Web Services | "
                                   "Beijing, China."), None
    if number == 22:
        steps = login_steps("alice.j@test.com") + [nav(BASE + "/applicant/dashboard/applications")]
        return steps, f"The application for 'Software Development Engineer, AI Runtime' is in '{T22_AI_RUNTIME_STATUS}' status.", None
    if number == 23:
        steps = login_steps("bob.c@test.com") + [
            nav(BASE + "/applicant/dashboard/applications"),
            clk(BASE + "/applicant/dashboard/applications", 5, "Withdraw")]
        return (steps, "I withdrew the application in Assessment status; it was for the job "
                "'Senior Product Manager, AU Customer Experience (CX) Improvement'.", mutate_t23)
    if number == 24:
        steps = login_steps("carol.d@test.com") + [
            nav(BASE + "/applicant/job-alerts"),
            inp(BASE + "/applicant/job-alerts", 0, T24_ALERT_QUERY),
            clk(BASE + "/applicant/job-alerts", 1, "Create alert")]
        return steps, f"The new 'product designer' job alert lists {T24_MATCH} matching jobs.", mutate_t24
    if number == 25:
        steps = login_steps("david.k@test.com") + [
            nav(BASE + "/user/details/edit"),
            inp(BASE + "/user/details/edit", 0, T25_HEADLINE),
            clk(BASE + "/user/details", 1, "Save changes"),
            nav(BASE + "/user/details")]
        return steps, f"The city shown in my profile is {T25_CITY}.", mutate_t25
    if number == 26:
        steps = login_steps("alice.j@test.com") + [
            nav(BASE + "/applicant/communication-preferences"),
            clk(BASE + "/applicant/communication-preferences", 0, "Job recommendations"),
            clk(BASE + "/applicant/communication-preferences", 1, "Save preferences")]
        return (steps, "After turning off Job recommendations emails, the remaining enabled email preference "
                "is Application updates; the Amazon Newsletter was already off.", mutate_t26)
    if number == 27:
        steps = login_steps("david.k@test.com") + [
            inp(BASE + "/", 0, "Applied Scientist, Leo Security"),
            clk(S + "?base_query=Applied+Scientist%2C+Leo+Security", 1, "search"),
            clk(BASE + f"/jobs/{T27_JOB}/applied-scientist-leo-security", 4, "first result"),
            clk(BASE + f"/applicant/jobs/{T27_JOB}/apply", 5, "Apply now"),
            clk(BASE + "/applicant/dashboard/applications", 6, "Submit application")]
        return steps, "I applied to the 'Applied Scientist, Leo Security' job; it shows the status 'Submitted'.", mutate_t27
    if number == 28:
        steps = login_steps("bob.c@test.com") + [
            nav(BASE + "/applicant/job-alerts"),
            clk(BASE + "/applicant/job-alerts", 3, "Delete")]
        return steps, "After deleting the 'product manager' alert for Austin, 0 job alerts remain.", mutate_t28
    if number == 29:
        steps = [nav(BASE + "/"), nav(S),
                 clk(S + "?category=fulfillment-center-warehouse-associate", 2, "Fulfillment Center Warehouse Associate"),
                 clk(S + "?category=fulfillment-center-warehouse-associate&experience=Less+than+1+year", 2, "Less than 1 year")]
        return steps, f"{T29_FULFILLMENT_LT1} jobs match those filters.", None
    raise ValueError(number)


# ---------------------------------------------------------------- app-logic replicas for sanity
STOP_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
              "or", "is", "are", "be", "by", "from", "how", "what", "which", "that",
              "this", "me", "my", "jobs", "job", "amazon", "role", "team", "work",
              "experience", "years"}


def db_rows(sql, args=()):
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def tokenize(query):
    return [t for t in re.split(r"\W+", (query or "").lower())
            if len(t) > 1 and t not in STOP_WORDS]


def job_search(query, jobs):
    tokens = tokenize(query)
    if not tokens:
        return list(jobs)
    ranked = []
    for job in jobs:
        strong = " ".join(str(job.get(f) or "") for f in ("title", "category", "team", "company_name")).lower()
        medium = " ".join(str(job.get(f) or "") for f in ("city", "state", "country_name", "normalized_location", "description_short")).lower()
        weak = " ".join(str(job.get(f) or "") for f in ("description", "basic_qualifications", "preferred_qualifications")).lower()
        def score(tok):
            if tok in strong:
                return 3
            if tok in medium or tok in weak:
                return 2
            if any(w.startswith(tok) for w in strong.split()):
                return 1
            if any(w.startswith(tok) for w in medium.split() + weak.split()):
                return 1
            return 0
        scores = [score(t) for t in tokens]
        if all(s > 0 for s in scores) and sum(scores) >= 3:
            ranked.append((sum(scores), job["id"], job))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return [r[2] for r in ranked]


def location_match(jobs, kw):
    tokens = [t for t in re.split(r"\W+", (kw or "").lower()) if t]
    return [j for j in jobs if all(t in " ".join([j["city"] or "", j["state"] or "",
                j["country_name"] or "", j["normalized_location"] or ""]).lower() for t in tokens)]


# ---------------------------------------------------------------- the tests
class AmazonJobsVerifierContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global SEED_COPY
        cls.maxDiff = None
        SEED_COPY = Path(tempfile.mkdtemp(prefix="wh-aj-seed-")) / "seed.db"
        shutil.copy2(SEED, SEED_COPY)
        cls.seed_copy = SEED_COPY
        cls.tmp = Path(tempfile.mkdtemp(prefix="wh-aj-tests-"))

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
        noop = build_run(self.fresh(f"t{number}_noop"),
                         [nav(BASE + "/")], "")
        code, verdict = run_verifier(number, noop)
        self.assertNotEqual(code, 0, f"task {number} no-op must FAIL")
        self.assertFalse(verdict["pass"])
        # 3. wrong answer fails
        wrong = build_run(self.fresh(f"t{number}_wrong"), steps, "A wrong answer with no basis.", mutate=mutate)
        code, verdict = run_verifier(number, wrong)
        self.assertNotEqual(code, 0, f"task {number} wrong answer must FAIL")
        self.assertFalse(verdict["pass"])
        # 4. shortcut (correct answer, no required navigation) fails
        # task 21's only required page IS the homepage, so its shortcut case
        # visits a different mirror page and never the homepage.
        shortcut_nav = [nav(BASE + "/search")] if number == 21 else [nav(BASE + "/")]
        shortcut = build_run(self.fresh(f"t{number}_shortcut"), shortcut_nav, answer, mutate=mutate)
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

    # ---- ground-truth sanity against the frozen seed DB
    def test_ground_truth_search_counts(self):
        jobs = db_rows("SELECT * FROM jobs")
        self.assertEqual(len(job_search("data engineer", location_match(jobs, "Seattle"))), T0_SEATTLE_ENGINEER)
        self.assertEqual(sum(1 for j in jobs if j["schedule"] == "Part Time"), T1_PART_TIME)
        self.assertEqual(sum(1 for j in jobs if j["city"] == "Tokyo"), T3_TOKYO)
        self.assertEqual(sum(1 for j in jobs if j["team_slug"] == "advertising"), 31)
        self.assertEqual(sum(1 for j in jobs if j["team_slug"] == "devices-services"), 71)
        ops7 = [j for j in jobs if j["team_slug"] == "amazon-operations" and j["experience"] == "7+ years"]
        self.assertEqual(len(ops7), T7_OPS_7Y)
        fc = [j for j in jobs if j["category_slug"] == "fulfillment-center-warehouse-associate"
              and j["experience"] == "Less than 1 year"]
        self.assertEqual(len(fc), T29_FULFILLMENT_LT1)
        self.assertEqual(len(location_match(jobs, "Seattle")), T16_SEATTLE_HERO)
        self.assertEqual(len(job_search("product designer", jobs)), T24_MATCH)

    def test_ground_truth_sort_anchors(self):
        jobs = db_rows("SELECT * FROM jobs")
        hw = [j for j in jobs if j["category_slug"] == "hardware-development"]
        hw.sort(key=lambda j: j["posted_sort"], reverse=True)
        self.assertEqual(hw[0]["title"], T2_FIRST_RECENT)
        ds = [j for j in jobs if j["category_slug"] == "data-science" and j["country_name"] == "India"]
        ds.sort(key=lambda j: j["posted_sort"], reverse=True)
        self.assertEqual(ds[0]["job_id"], T5_JOB)
        self.assertEqual(ds[0]["company_name"], T5_COMPANY)
        self.assertIn("ADCI", ds[0]["company_name"])
        sea = location_match(jobs, "Seattle")
        sea.sort(key=lambda j: j["posted_sort"], reverse=True)
        self.assertEqual(sea[0]["title"], T16_MOST_RECENT)
        interns = [j for j in jobs if j["is_intern"] == 1 and j["country_name"] == "India"]
        interns.sort(key=lambda j: j["posted_sort"], reverse=True)
        self.assertEqual(interns[0]["job_id"], T6_JOB)
        self.assertEqual(interns[0]["company_name"], T6_COMPANY)

    def test_ground_truth_job_anchors(self):
        jobs = {j["job_id"]: j for j in db_rows("SELECT * FROM jobs")}
        self.assertEqual(jobs[T8_JOB]["company_name"], "Amazon Web Services, Inc.")
        self.assertIn("scalable design systems", jobs[T9_JOB]["preferred_qualifications"])
        self.assertIn("Bachelor's degree", jobs[T10_JOB_B]["preferred_qualifications"])
        self.assertNotIn("degree", jobs[T10_JOB_A]["preferred_qualifications"])
        self.assertEqual((jobs[T11_JOB]["country_code"], jobs[T11_JOB]["state"], jobs[T11_JOB]["city"]),
                         ("AUS", "NSW", "Sydney"))
        self.assertEqual(jobs[T27_JOB]["id"], T27_JOB_PK)

    def test_ground_truth_content_anchors(self):
        cat = db_rows("SELECT * FROM categories WHERE slug='software-development'")[0]
        sections = json.loads(cat["sections_json"])
        self.assertEqual(sections[0]["heading"], T12_SWDEV_FIRST_SECTION)
        voices = json.loads(cat["voices_json"])
        self.assertEqual(len(voices), T13_VOICES)
        self.assertEqual(voices[0]["name"], T13_FIRST_NAME)
        self.assertEqual(db_rows("SELECT COUNT(*) c FROM jobs WHERE category_slug='marketing'")[0]["c"],
                         T14_MARKETING_OPEN)
        us = db_rows("SELECT COUNT(*) c FROM location_pages WHERE region='United States'")[0]["c"]
        self.assertEqual(us, T15_US_LOCATIONS)
        aws = db_rows("SELECT * FROM teams WHERE slug='amazon-web-services'")[0]
        self.assertIn("AWS Infrastructure Services (AIS) team", aws["blocks_json"])
        faq = db_rows("SELECT answer FROM faq_items WHERE question='Where can I find open roles?'")[0]
        self.assertIn("encourage you to use this website", faq["answer"])
        self.assertIn("filter your search by locations, business categories, job categories, or keywords", faq["answer"])
        benefits = [r["heading"] for r in db_rows("SELECT heading FROM benefit_sections ORDER BY \"order\"")]
        self.assertIn(T19_TIME_AWAY, benefits)
        hwh = [r["heading"] for r in db_rows(
            "SELECT heading FROM content_blocks WHERE page='how_we_hire' ORDER BY \"order\"")]
        self.assertEqual(len(hwh), T20_STEPS)
        self.assertEqual(hwh[0], T20_FIRST_STEP)
        story = db_rows("SELECT * FROM employee_stories ORDER BY \"order\" LIMIT 1")[0]
        self.assertEqual(story["name"], "Xiaole")
        self.assertEqual(story["role"], "Engineer")
        self.assertEqual(story["location"], "Beijing, China")

    def test_ground_truth_account_anchors(self):
        apps = db_rows("""SELECT a.status, j.job_id, j.title, u.email FROM applications a
                          JOIN jobs j ON j.id=a.job_id JOIN users u ON u.id=a.user_id""")
        ai = [a for a in apps if a["email"] == "alice.j@test.com" and "AI Runtime" in a["title"]]
        self.assertEqual(len(ai), 1)
        self.assertEqual(ai[0]["status"], T22_AI_RUNTIME_STATUS)
        bob_asmt = [a for a in apps if a["email"] == "bob.c@test.com" and a["status"] == "Assessment"]
        self.assertEqual(len(bob_asmt), 1)
        self.assertEqual(bob_asmt[0]["title"], "Senior Product Manager, AU Customer Experience (CX) Improvement")
        self.assertEqual(bob_asmt[0]["job_id"], "10498057")
        david = db_rows("SELECT * FROM users WHERE email='david.k@test.com'")[0]
        self.assertEqual(david["city"], T25_CITY)
        self.assertEqual(david["headline"], "Data Scientist")
        alice = db_rows("SELECT * FROM users WHERE email='alice.j@test.com'")[0]
        self.assertEqual((alice["notify_recommendations"], alice["notify_application_updates"],
                          alice["notify_newsletter"]), (1, 1, 0))
        bob_alerts = db_rows("SELECT * FROM job_alerts WHERE user_id=2")
        self.assertEqual(len(bob_alerts), 1)
        self.assertEqual(bob_alerts[0]["query_text"], "product manager")
        david_apps = [a for a in apps if a["email"] == "david.k@test.com" and a["job_id"] == T27_JOB]
        self.assertEqual(david_apps, [])

    def test_answers_predicates(self):
        self.assertTrue(answers.devices_wins("Devices and Services has more open jobs (71 vs 31)."))
        self.assertFalse(answers.devices_wins("Amazon Ads has more open jobs (71 vs 31)."))
        self.assertFalse(answers.devices_wins("Amazon Ads has more open jobs than Devices and Services."))
        self.assertTrue(answers.scalable_design_systems("The job asks for experience working with scalable design systems."))
        self.assertFalse(answers.scalable_design_systems("The job asks for experience with ETL pipelines."))
        self.assertTrue(answers.elevated_mentions_degree("The UX Designer, Elevated Shopping Experience job mentions the degree."))
        self.assertTrue(answers.degree_field("a Bachelor's degree or above in design, human-computer interaction (HCI)"))
        self.assertFalse(answers.degree_field("a Bachelor's degree in finance"))
        self.assertTrue(answers.uses_this_site("Amazon encourages you to use this website to find open roles."))
        self.assertTrue(answers.filter_dims("filter by locations, business categories, job categories, or keywords", 2))
        self.assertFalse(answers.filter_dims("filter by salary only", 2))
        self.assertTrue(answers.application_updates_remain("Application updates remains enabled."))
        self.assertFalse(answers.job_recommendations_still_on("Application updates remains enabled."))
        self.assertTrue(answers.job_recommendations_still_on("Job recommendations remains enabled."))
        self.assertTrue(answers.zero_alerts("0 job alerts remain."))
        self.assertTrue(answers.zero_alerts("No job alerts remain on the page."))
        self.assertFalse(answers.zero_alerts("Two alerts remain."))
        self.assertTrue(answers.au_cx_title("It was for 'Senior Product Manager, AU Customer Experience (CX) Improvement'."))
        self.assertFalse(answers.au_cx_title("It was for 'Data Engineer'."))
        self.assertTrue(answers.ais_team("The AWS Infrastructure Services (AIS) team handles it."))
        self.assertFalse(answers.ais_team("The AWS sales team handles it."))
        self.assertTrue(answers.adci_company("The company is ADCI - Karnataka - A66."))
        self.assertTrue(answers.xiaole_story("The story is about Xiaole, an Engineer based in Beijing, China."))
        self.assertFalse(answers.xiaole_story("The story is about Dwight in Sunnyvale."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
