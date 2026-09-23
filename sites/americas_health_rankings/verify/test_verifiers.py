"""Deterministic verifier contract tests for the americas_health_rankings mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (measure slices, state
    tables, seeded bookmark sets, download lists, FAQ wording),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - a tampered run package (missing/corrupt trajectory, missing or 1x1
    screenshots, mutated after-DB) MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed.
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
SEED = SITE / "instance_seed" / "americas_health_rankings.db"

sys.path.insert(0, str(VERIFY))
from grade import (T0_TOP, T1_BOTTOM, T2_2011, T2_LATEST, T3_WORST, T4_TOP,  # noqa: E402
                   T5_MT, T6_SOURCE, T7_TOP3, T8_CA, T9_TOP, T10_CA_ANNUAL,
                   T11_CA_SENIOR, T12_MEASURE, T12_RANK, T13_CHALLENGES,
                   T14_NH_PE, T15_STRENGTHS, T16_COUNT, T16_TITLES,
                   T17_FIRST, T17_LAST, T18_MAPS, T18_COUNT, T19_CA_CS,
                   T23_TOKENS, T24_COUNT, T24_MEASURES, T25_CATEGORY,
                   T26_MEASURES, T27_FINAL_COUNT, T28_REMAINING, T34_TITLE,
                   T29_NAME, T29_EMAIL, T30_NAME, T30_EMAIL, T30_ORG,
                   T31_NAMES, T32_WHO, T33_TOKENS, ALICE, BOB, CAROL)

BASE = "http://localhost:46058"


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
        env={**os.environ, "WH_SITE": "americas_health_rankings"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-500:],
                   "stderr": proc.stderr[-500:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def mut_t28(db):
    """Bob removed the frequent mental distress bookmark."""
    con = sqlite3.connect(db)
    con.execute("DELETE FROM bookmarks WHERE user_id=(SELECT id FROM users WHERE email=?) "
                "AND kind='measure' AND item_slug='mental_distress'", (BOB,))
    con.commit(); con.close()


def mut_t29(db):
    """Newsletter signup row for Jordan Lee."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM newsletter_signups").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO newsletter_signups (id, name, email, created_at) VALUES (?,?,?,?)",
                (nid, T29_NAME, T29_EMAIL, "2026-09-21 12:00:00"))
    con.commit(); con.close()


def mut_t30(db):
    """Inquiry row for Dana Torres."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM inquiries").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO inquiries (id, name, email, phone, organization, comment, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (nid, T30_NAME, T30_EMAIL, "", T30_ORG,
                 "Can the state-level measure data be reused in a research paper?",
                 "2026-09-21 12:00:00"))
    con.commit(); con.close()


def mut_t34(db):
    """Carol saved the Montana state page."""
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM bookmarks").fetchone()[0] or 0) + 1
    uid = con.execute("SELECT id FROM users WHERE email=?", (CAROL,)).fetchone()[0]
    con.execute("INSERT INTO bookmarks (id, user_id, kind, item_slug, title, created_at) "
                "VALUES (?,?,?,?,?,?)", (nid, uid, "state", "MT", T34_TITLE, "2026-09-21 12:00:00"))
    con.commit(); con.close()


# ---------------------------------------------------------------- honest steps
def S(url, action="navigate", params=None, text=""):
    return (url, action, params or {}, text)


M = BASE + "/explore/measures/"
R = BASE + "/publications/reports/2025-annual-report/"

HONEST = {
    0: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "teen_suicide", text="Teen Suicide in United States Top States: New Jersey 1 5.1"),
        ], answer="The top-ranked state for Teen Suicide is New Jersey, with a value of 5.1 deaths per 100,000 adolescents ages 15-19."),
    1: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "Obesity", text="Obesity in United States Bottom States: West Virginia 49 41.4%"),
        ], answer="West Virginia is ranked last in the nation for obesity (rank 49 of the ranked states), with an obesity value of 41.4%."),
    2: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "mental_distress", text="Frequent Mental Distress Trends United States 2011 11.7 2024 15.6"),
        ], answer="The U.S. frequent mental distress value was 11.7% in 2011 and 15.6% in the most recent year shown (2024)."),
    3: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "air", text="Air Pollution in United States Bottom States: California 50 11.7"),
        ], answer="California has the worst air pollution ranking in the nation, with a value of 11.7 micrograms of fine particles per cubic meter."),
    4: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "MHP", text="Mental Health Providers in United States Top States: Alaska 1 822.0"),
        ], answer="Alaska has the highest number of mental health providers per 100,000 population, with a value of 822.0."),
    5: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "ExcessDrink", text="Excessive Drinking View All States Montana 49 22.5%"),
        ], answer="Montana's excessive drinking value is 22.5%, ranked 49th in the nation."),
    6: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "hb_water_violation", text="Drinking Water Violations Data Source: U.S. Environmental Protection Agency, Office of Enforcement and Compliance Assurance, Safe Drinking Water Information System via Enforcement and Compliance History Online (ECHO)"),
        ], answer="The data source for the Drinking Water Violations measure is the U.S. Environmental Protection Agency, Office of Enforcement and Compliance Assurance, Safe Drinking Water Information System via Enforcement and Compliance History Online (ECHO)."),
    7: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "birthweight", text="Low Birth Weight Top States: Alaska 1 6.7% New Hampshire 2 6.8% Idaho 3 6.9%"),
        ], answer="The three top-ranked states with the lowest low birth weight rates are Alaska (6.7%), New Hampshire (6.8%) and Idaho (6.9%)."),
    8: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "Obesity?view=all", text="Obesity full state rankings California 29.1% rank 6"),
        ], answer="California's obesity value is 29.1%, ranked 6th in the nation."),
    9: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(M + "Smoking", text="Smoking in United States Top States: Utah 1 5.7%"),
        ], answer="Utah has the lowest adult smoking rate in the nation, with a value of 5.7%."),
    10: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/CA", text="Summary of California California's 2025 Annual Report Ranking: #24"),
        ], answer="California's overall health ranking in the 2025 Annual Report is #24."),
    11: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/CA", text="Summary of California California's 2025 Annual Report Ranking: #24"),
            S(BASE + "/explore/states/CA?rank=senior", "select_dropdown", {"rank": "senior"},
              text="Summary of California California's 2026 Senior Report Ranking: #20"),
        ], answer="In the Senior Report edition, California's overall rank is #20."),
    12: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/TX", text="Summary of Texas Texas's 2025 Annual Report Ranking: #40 Top Positive Impact 1. Premature Death Racial Disparity rank 4"),
        ], answer="The measure with the most positive impact on Texas's 2025 Annual Report ranking is Premature Death Racial Disparity, and Texas ranks 4th on that measure."),
    13: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/MA", text="Summary of Massachusetts Challenges: High income inequality, High preventable hospitalization rate, High prevalence of households experiencing severe housing problems"),
        ], answer="The three challenges shown for Massachusetts are: high income inequality, high preventable hospitalization rate, and high prevalence of households experiencing severe housing problems."),
    14: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/NH", text="Summary of New Hampshire Physical Environment 0.513 9"),
        ], answer="New Hampshire's Physical Environment score in the 2025 Annual Report is 0.513, ranked 9th."),
    15: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage"),
            S(BASE + "/explore/states/MT", text="Summary of Montana Strengths: Low prevalence of obesity, High prevalence of high school completion, Low incidence of chlamydia"),
        ], answer="The three strengths shown for Montana are: low prevalence of obesity, high prevalence of high school completion, and low incidence of chlamydia."),
    16: dict(steps=[
            S(BASE + "/publications", text="Publications hub"),
            S(BASE + "/publications/reports/2025-annual-report",
              text="2025 Annual Report Downloads: 2025 Annual Report, Executive Brief, State Summaries, Economic Hardship Index County-Level Maps, Measures Table, Infographics, Report Data (All States)"),
        ], answer="The 2025 Annual Report main page offers 7 download options: the 2025 Annual Report, the Executive Brief, the State Summaries, the Economic Hardship Index County-Level Maps, the Measures Table, the Infographics, and the Report Data (All States)."),
    17: dict(steps=[
            S(R, text="2025 Annual Report Overview"),
            S(R + "state-rankings", text="State Rankings New Hampshire No. 1 Louisiana No. 50"),
        ], answer="New Hampshire is ranked No. 1 and Louisiana is ranked No. 50 in the overall state rankings."),
    18: dict(steps=[
            S(BASE + "/publications", text="Publications hub"),
            S(BASE + "/publications/reports/2026-senior-report",
              text="2026 Senior Report Downloads: 2026 Senior Report, Executive Brief, State Summaries, Risk of Social Isolation County-Level Maps, Measures Table, Infographics, Report Data (All States)"),
        ], answer="The county-level maps download is titled \"2026 Senior Report - Risk of Social Isolation County-Level Maps\", and the report's main page offers 7 download options in total."),
    19: dict(steps=[
            S(R, text="2025 Annual Report Overview"),
            S(R + "state-summaries-california", text="California state summary Cancer Screenings 58.5% 45"),
        ], answer="For Cancer Screenings, California shows a value of 58.5% and a rank of 45."),
    20: dict(steps=[
            S(R, text="2025 Annual Report Overview"),
            S(R + "appendix-measures-table", text="Measures Table Smoking U.S. HHS, CDC, Behavioral Risk Factor Surveillance System 2024"),
        ], answer="The survey data source listed for the Smoking measure is the U.S. HHS, CDC, Behavioral Risk Factor Surveillance System (2024)."),
    21: dict(steps=[
            S(BASE + "/publications/articles", text="Publication Articles"),
            S(BASE + "/publications/articles/documenting-the-human-experience-means-measuring-caregiving",
              text="The new caregiver data featured in this year's Senior Report. Our organization, the National Alliance for Caregiving (NAC)"),
        ], answer="(a) The author says the new caregiver data is featured in this year's Senior Report; (b) he uses the abbreviation NAC for the National Alliance for Caregiving."),
    22: dict(steps=[
            S(BASE + "/publications/articles", text="Publication Articles From Data to Action by Joseph Kanter"),
            S(BASE + "/publications/articles/from-data-to-action-how-states-can-use-americas-health-rankings-to-drive-and-measure-progress",
              text="For more than three decades, America's Health Rankings has served as a vital resource for states and other stakeholders"),
        ], answer="According to the article, America's Health Rankings has served as a vital resource for states and other stakeholders for more than three decades."),
    23: dict(steps=[
            S(BASE + "/search?q=cancer+screenings", text="Search results for cancer screenings Cancer Screenings"),
            S(M + "health_screenings_ahr",
              text="Cancer Screenings Percentage of women ages 40-74 who reported receiving a mammogram in the past two years and percentage of adults ages 45-75 who reported receiving colorectal cancer screening within the recommended time period"),
        ], answer="The full definition of the Cancer Screenings measure: percentage of women ages 40-74 who reported receiving a mammogram in the past two years and percentage of adults ages 45-75 who reported receiving colorectal cancer screening within the recommended time period."),
    24: dict(steps=[
            S(BASE + "/explore/measures", text="Explore Health Measures Behavioral Health: Depression, Drug Deaths, Excessive Drinking, Flourishing - Children, Frequent Mental Distress, Mental Health Conditions (Diagnosed) - Children, Non-Medical Drug Use - Past Year, Postpartum Anxiety, Postpartum Depression, Suicide"),
        ], answer="The Behavioral Health category lists 10 measures: Depression, Drug Deaths, Excessive Drinking, Flourishing - Children, Frequent Mental Distress, Mental Health Conditions (Diagnosed) - Children, Non-Medical Drug Use - Past Year, Postpartum Anxiety, Postpartum Depression, and Suicide."),
    25: dict(steps=[
            S(BASE + "/explore/measures", text="Explore Health Measures Additional Older Adult Measures Suicide - Age 65+"),
        ], answer="The measure 'Suicide - Age 65+' is listed under the Additional Older Adult Measures category."),
    26: dict(steps=[
            S(BASE + "/explore/measures", text="Explore Health Measures Sleep Health: Insufficient Sleep, Sleep Position"),
        ], answer="The Sleep Health category lists two measures: Insufficient Sleep and Sleep Position."),
    27: dict(steps=[
            S(BASE + "/login", "input", {"email": ALICE, "password": "TestPass123!"},
              text="You have been logged in."),
            S(M + "teen_suicide", "click", text="Teen Suicide Save this measure"),
            S(M + "teen_suicide", "click", text="Saved to your account. Teen Suicide Saved ✓ (remove)"),
            S(BASE + "/account/saved", "click", text="Saved Items Teen Suicide Frequent Mental Distress Obesity"),
            S(M + "teen_suicide", "click", text="Removed from your saved items. Teen Suicide Save this measure"),
            S(BASE + "/account/saved", "click", text="Saved Items Frequent Mental Distress Obesity 2 items"),
        ], answer="After saving and then removing the Teen Suicide measure, my saved list has 2 items: Frequent Mental Distress and Obesity."),
    28: dict(steps=[
            S(BASE + "/login", "input", {"email": BOB, "password": "TestPass123!"},
              text="You have been logged in."),
            S(BASE + "/account/saved", "click", text="Saved Items California Frequent Mental Distress Obesity"),
            S(M + "mental_distress", "click", text="Frequent Mental Distress Saved (remove)"),
            S(BASE + "/account/saved", "click", text="Saved Items California Obesity"),
        ], answer="I removed the frequent mental distress measure; the remaining saved items are California and Obesity.", mutate=mut_t28),
    29: dict(steps=[
            S(BASE + "/", text="America's Health Rankings homepage with the footer newsletter signup form"),
            S(BASE + "/", "input", {"name": T29_NAME, "email": T29_EMAIL},
              text="Thank you for signing up for updates."),
        ], answer="The confirmation message was: \"Thank you for signing up for updates.\"", mutate=mut_t29),
    30: dict(steps=[
            S(BASE + "/about/page/submit-an-inquiry", text="Submit An Inquiry form"),
            S(BASE + "/about/page/submit-an-inquiry", "input",
              {"your name": T30_NAME, "email": T30_EMAIL, "confirm email": T30_EMAIL,
               "your organization": T30_ORG,
               "your comment": "Can the state-level measure data be reused in a research paper?"},
              text="Thank you. Your inquiry has been submitted."),
        ], answer="The confirmation shown after submission was: \"Thank you. Your inquiry has been submitted.\"", mutate=mut_t30),
    31: dict(steps=[
            S(BASE + "/faq", text="FAQs How often are America's Health Rankings reports updated? We release three state health ranking reports annually: the Annual Report, the Senior Report and the Health of Women and Children Report."),
        ], answer="America's Health Rankings releases three state health ranking reports each year: the Annual Report, the Senior Report, and the Health of Women and Children Report."),
    32: dict(steps=[
            S(BASE + "/faq", text="FAQs Who guides the America's Health Rankings reports? Each report is guided by an Advisory Committee that convenes annually."),
        ], answer="According to the FAQ, each report is guided by an Advisory Committee that convenes annually."),
    33: dict(steps=[
            S(BASE + "/health-topics", text="Health Topics Senior Health Explore the 50+ measures in the Senior Report."),
        ], answer="The description given for the 'Senior Health' topic is: \"Explore the 50+ measures in the Senior Report.\""),
    34: dict(steps=[
            S(BASE + "/login", "input", {"email": CAROL, "password": "TestPass123!"},
              text="You have been logged in."),
            S(BASE + "/explore/states/MT", "click", text="Summary of Montana Save this state"),
            S(BASE + "/account/saved", "click", text="Saved Items Montana Frequent Mental Distress Obesity"),
        ], answer="The saved item is shown with the title \"Montana\" on my Saved Items page.", mutate=mut_t34),
}

# Reviewed request fixtures are synthetic controls based on checked browser paths.
for _number, _fixture in json.loads((VERIFY / "reviewed_fixtures.json").read_text()).items():
    HONEST[int(_number)]["answer"] = _fixture["answer"]
    HONEST[int(_number)]["steps"] = [
        S(BASE + step["path"], step["action"], step["params"], step["text"])
        for step in _fixture["steps"]
    ]

WRONG_ANSWER = {
    0: "The top-ranked state for Teen Suicide is Massachusetts, with a value of 5.3.",
    1: "Mississippi is ranked last in the nation for obesity, with a value of 34.5%.",
    2: "The U.S. frequent mental distress value was 12.4% in 2011 and 13.8% in the most recent year.",
    3: "Pennsylvania has the worst air pollution ranking, with a value of 11.0 micrograms per cubic meter.",
    4: "Massachusetts has the most mental health providers per 100,000 population, with a value of 813.9.",
    5: "Montana's excessive drinking value is 21.8%, ranked 42nd.",
    6: "The data source is the CDC Behavioral Risk Factor Surveillance System.",
    7: "The three top states for low birth weight are Oregon, Washington and Minnesota.",
    8: "California's obesity value is 24.7%, ranked 10th.",
    9: "Colorado has the lowest adult smoking rate, with a value of 10.5%.",
    10: "California's overall health ranking in the 2025 Annual Report is #12.",
    11: "In the Senior Report edition, California's overall rank is #33.",
    12: "The measure with the most positive impact on Texas's ranking is Smoking, and Texas ranks 14th on it.",
    13: "The challenges for Massachusetts are high obesity, low immunization coverage and high drug deaths.",
    14: "New Hampshire's Physical Environment score is -0.507, ranked 50th.",
    15: "The strengths for Montana are low smoking, high vaccination coverage and low air pollution.",
    16: "The report page offers 5 download options.",
    17: "Massachusetts is ranked No. 1 and Mississippi is ranked No. 50.",
    18: "The county-level maps download is titled \"Economic Hardship Index County-Level Maps\", and there are 4 downloads.",
    19: "Cancer Screenings shows a value of 47.3% and a rank of 50 for California.",
    20: "The survey data source for Smoking is the American Community Survey.",
    21: "The caregiver data is featured in the Annual Report, and the author's abbreviation is UHF.",
    22: "America's Health Rankings has served as a vital resource for two decades.",
    23: "The definition is the percentage of adults who reported smoking at least 100 cigarettes.",
    24: "The Behavioral Health category lists 8 measures, including Depression and Suicide.",
    25: "The 'Suicide - Age 65+' measure is under the Behavioral Health category.",
    26: "The Sleep Health category lists Insufficient Sleep and Adequate Sleep.",
    27: "After saving and removing, my saved list has 3 items.",
    28: "I removed the Frequent Mental Distress measure; the only remaining saved item is California.",
    29: "The confirmation said my inquiry was submitted.",
    30: "The confirmation said thanks for signing up for updates.",
    31: "America's Health Rankings releases two reports each year: the Annual Report and the Senior Report.",
    32: "Each report is guided by the United Health Foundation.",
    33: "The Senior Health topic says it covers the 100+ measures in the Health of Women and Children Report.",
    34: "The saved item is shown with the title \"MT\".",
}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ahr-verify-tests-")
        cls.root = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fresh(self, name):
        d = self.root / name
        if d.exists():
            shutil.rmtree(d)
        return d

    # ---------------- honest fixtures ----------------
    def test_honest_runs_all_pass(self):
        failures = []
        for n in range(35):
            spec = HONEST[n]
            d = build_run(self.fresh(f"honest_{n}"), spec["steps"], spec["answer"],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc != 0 or not verdict.get("pass"):
                failures.append((n, verdict.get("reason"),
                                 [e for e in verdict.get("evidence", []) if e.startswith("[FAIL]")][:4]))
        self.assertEqual(failures, [], f"honest fixtures must pass: {failures}")

    # ---------------- no-op ----------------
    def test_noop_runs_all_fail(self):
        misses = []
        for n in range(35):
            d = build_run(self.fresh(f"noop_{n}"), [S(BASE + "/")], "")  # empty answer, no navigation
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append(n)
        self.assertEqual(misses, [], f"no-op runs must fail everywhere: {misses}")

    def test_noop_with_answer_fails(self):
        """Answer without any task-relevant navigation still fails (anti-guess)."""
        misses = []
        for n in range(35):
            spec = HONEST[n]
            d = build_run(self.fresh(f"noopans_{n}"), [S(BASE + "/")], spec["answer"])
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append(n)
        self.assertEqual(misses, [], f"homepage-only runs must fail: {misses}")

    # ---------------- wrong answers ----------------
    def test_wrong_answers_fail(self):
        misses = []
        for n in range(35):
            spec = HONEST[n]
            d = build_run(self.fresh(f"wrong_{n}"), spec["steps"], WRONG_ANSWER[n],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append((n, verdict.get("reason")))
        self.assertEqual(misses, [], f"wrong answers must fail: {misses}")

    # ---------------- shortcuts ----------------
    def test_shortcut_runs_fail(self):
        """Correct answer + correct DB state, but only the homepage was opened."""
        misses = []
        for n in range(35):
            spec = HONEST[n]
            shortcut_steps = [S(BASE + "/")]
            d = build_run(self.fresh(f"shortcut_{n}"), shortcut_steps, spec["answer"],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append((n, verdict.get("reason")))
        self.assertEqual(misses, [], f"shortcut runs must fail: {misses}")

    # ---------------- tampered packages ----------------
    def test_missing_trajectory_fails(self):
        d = build_run(self.fresh("missing_traj"), HONEST[3]["steps"], HONEST[3]["answer"])
        (d / "trajectory.json").unlink()
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_corrupt_trajectory_fails(self):
        d = build_run(self.fresh("corrupt_traj"), HONEST[3]["steps"], HONEST[3]["answer"])
        (d / "trajectory.json").write_text("{not json")
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_missing_screenshots_fail(self):
        d = build_run(self.fresh("missing_shots"), HONEST[3]["steps"], HONEST[3]["answer"])
        shutil.rmtree(d / "screenshots")
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_tiny_screenshots_fail(self):
        d = build_run(self.fresh("tiny_shots"), HONEST[3]["steps"], HONEST[3]["answer"])
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(make_png(1, width=1, height=1))
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_identical_frames_fail(self):
        d = build_run(self.fresh("same_shots"), HONEST[3]["steps"], HONEST[3]["answer"])
        frame = make_png(7)
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(frame)
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_readonly_db_tamper_fails(self):
        d = build_run(self.fresh("tamper_ro"), HONEST[3]["steps"], HONEST[3]["answer"])
        con = sqlite3.connect(d / "after.db")
        con.execute("UPDATE measures SET display_name='Hacked' WHERE id=1")
        con.commit(); con.close()
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_stateful_extra_mutation_fails(self):
        d = build_run(self.fresh("tamper_st"), HONEST[28]["steps"], HONEST[28]["answer"],
                      mutate=mut_t28)
        con = sqlite3.connect(d / "after.db")
        con.execute("UPDATE users SET name='Hacked' WHERE email=?", (ALICE,))
        con.commit(); con.close()
        rc, verdict = run_verifier(28, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_stateful_missing_mutation_fails(self):
        """Agent self-reports success but the DB is unchanged."""
        d = build_run(self.fresh("missing_mut"), HONEST[28]["steps"], HONEST[28]["answer"])
        rc, verdict = run_verifier(28, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_t27_visit_only_shortcut_fails(self):
        """T27 save-then-remove is DB-invariant: an informed agent that visits
        all the right pages but never saves/removes must still FAIL - the
        trajectory must carry the rendered save and remove confirmations."""
        shortcut = [
            S(BASE + "/login", "input", {"email": ALICE, "password": "TestPass123!"},
              text="You have been logged in."),
            S(M + "teen_suicide", "navigate", text="Teen Suicide Save this measure"),
            S(BASE + "/account/saved", "navigate",
              text="Saved Items Frequent Mental Distress Obesity"),
        ]
        d = build_run(self.fresh("t27_visitonly"), shortcut, HONEST[27]["answer"])
        rc, verdict = run_verifier(27, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))
        reasons = [e for e in verdict.get("evidence", []) if e.startswith("[FAIL]")]
        self.assertTrue(any("save_action_evidence" in e for e in reasons), reasons)
        self.assertTrue(any("remove_action_evidence" in e for e in reasons), reasons)

    def test_upstream_origin_fails(self):
        steps = [S("https://www.americashealthrankings.org/explore/measures/air", "navigate")]
        d = build_run(self.fresh("upstream"), steps, HONEST[3]["answer"])
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_truncated_run_fails(self):
        d = build_run(self.fresh("truncated"), HONEST[3]["steps"], HONEST[3]["answer"],
                      terminated=False)
        rc, verdict = run_verifier(3, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_wrong_user_state_change_fails(self):
        """T28: bob's target row removed but david's copy also removed (over-delete)."""
        def over_delete(db):
            mut_t28(db)
            con = sqlite3.connect(db)
            con.execute("DELETE FROM bookmarks WHERE user_id=(SELECT id FROM users WHERE email=?) "
                        "AND kind='measure' AND item_slug='mental_distress'", ("david.k@test.com",))
            con.commit(); con.close()
        d = build_run(self.fresh("overdel"), HONEST[28]["steps"], HONEST[28]["answer"],
                      mutate=over_delete)
        rc, verdict = run_verifier(28, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))


class GroundTruthTests(unittest.TestCase):
    """The hardcoded ground truth must match the frozen seed DB."""

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def q(self, sql, params=()):
        return self.con.execute(sql, params).fetchall()

    def current(self, slug):
        m = self.q("SELECT id, latest_year FROM measures WHERE slug=?", (slug,))[0]
        rows = self.q("""SELECT mv.rank, mv.value, mv.value_display, s.name FROM measure_values mv
            JOIN states s ON s.code=mv.state_code
            WHERE mv.measure_id=? AND mv.display_year=? AND mv.state_code!='ALL' AND mv.rank IS NOT NULL
            ORDER BY mv.rank""", (m["id"], m["latest_year"]))
        return m, rows

    def test_seed_counts(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM measures")[0][0], 287)
        self.assertEqual(self.q("SELECT COUNT(*) FROM states")[0][0], 52)
        self.assertEqual(self.q("SELECT COUNT(*) FROM reports")[0][0], 43)
        self.assertEqual(self.q("SELECT COUNT(*) FROM users")[0][0], 4)
        self.assertEqual(self.q("SELECT COUNT(*) FROM bookmarks")[0][0], 10)
        self.assertEqual(self.q("SELECT COUNT(*) FROM faq_items")[0][0], 6)

    def test_t0_teen_suicide_top(self):
        m, rows = self.current("teen_suicide")
        self.assertEqual(m["latest_year"], "2021-2023")
        self.assertEqual((rows[0]["name"], rows[0]["value"]), T0_TOP)

    def test_t1_t8_obesity_anchors(self):
        m, rows = self.current("Obesity")
        self.assertEqual(m["latest_year"], "2024")   # fixed multi-series slice (R1)
        self.assertEqual((rows[-1]["name"], rows[-1]["value"]), T1_BOTTOM)
        self.assertEqual(rows[-1]["rank"], 49)
        ca = self.q("""SELECT mv.value, mv.rank FROM measure_values mv
            JOIN measures m ON m.id=mv.measure_id WHERE m.slug='Obesity'
            AND mv.display_year=m.latest_year AND mv.state_code='CA'""")[0]
        self.assertEqual((ca["value"], ca["rank"]), T8_CA)

    def test_t2_mental_distress_trend(self):
        m = self.q("SELECT id, latest_year FROM measures WHERE slug='mental_distress'")[0]
        y2011 = self.q("SELECT value FROM measure_values WHERE measure_id=? AND state_code='ALL' AND display_year='2011'",
                       (m["id"],))[0]["value"]
        latest = self.q("SELECT value FROM measure_values WHERE measure_id=? AND state_code='ALL' AND display_year=?",
                        (m["id"], m["latest_year"]))[0]["value"]
        self.assertEqual((y2011, latest), (T2_2011, T2_LATEST))

    def test_t3_t9_measure_anchors(self):
        _, air = self.current("air")
        self.assertEqual((air[-1]["name"], air[-1]["value"]), T3_WORST)
        self.assertEqual(air[-1]["rank"], 50)
        _, mhp = self.current("MHP")
        self.assertEqual((mhp[0]["name"], mhp[0]["value"]), T4_TOP)
        m5 = self.q("SELECT mv.value, mv.rank FROM measure_values mv JOIN measures m ON m.id=mv.measure_id "
                    "WHERE m.slug='ExcessDrink' AND mv.display_year=m.latest_year AND mv.state_code='MT'")[0]
        self.assertEqual((m5["value"], m5["rank"]), T5_MT)
        _, smoking = self.current("Smoking")
        self.assertEqual((smoking[0]["name"], smoking[0]["value"]), T9_TOP)

    def test_t6_water_violation_source(self):
        m = self.q("SELECT source_name FROM measures WHERE slug='hb_water_violation'")[0]
        for token in T6_SOURCE:
            self.assertIn(token, m["source_name"].lower())

    def test_t7_birthweight_top3(self):
        _, rows = self.current("birthweight")
        got = [(r["name"], r["value"]) for r in rows[:3]]
        self.assertEqual(got, T7_TOP3)

    def test_t10_t14_state_table_anchors(self):
        r = self.q("SELECT value_display, rank FROM edition_measure_states WHERE state_code='CA' "
                   "AND edition_id=284 AND measure_slug='Overall'")[0]
        self.assertEqual(r["rank"], T10_CA_ANNUAL)
        r = self.q("SELECT value_display, rank FROM edition_measure_states WHERE state_code='CA' "
                   "AND edition_id=286 AND measure_slug='overall_sr_2'")[0]
        self.assertEqual(r["rank"], T11_CA_SENIOR)
        r = self.q("SELECT contribution, rank FROM edition_measure_states WHERE state_code='TX' "
                   "AND edition_id=284 AND is_core='C' AND contribution IS NOT NULL "
                   "ORDER BY contribution DESC LIMIT 1")[0]
        self.assertEqual(r["rank"], T12_RANK)
        r = self.q("SELECT value_display, rank FROM edition_measure_states WHERE state_code='NH' "
                   "AND edition_id=284 AND measure_slug='physical_environment'")[0]
        self.assertEqual((float(r["value_display"]), r["rank"]), T14_NH_PE)

    def test_t13_t15_state_facts(self):
        got = [r["content"].lower() for r in self.q(
            "SELECT content FROM state_facts WHERE state_code='MA' AND kind='challenge' ORDER BY position")]
        for token in T13_CHALLENGES:
            self.assertTrue(any(token in c for c in got), token)
        got = [r["content"].lower() for r in self.q(
            "SELECT content FROM state_facts WHERE state_code='MT' AND kind='strength' ORDER BY position")]
        self.assertEqual(len(got), 3)
        for token in T15_STRENGTHS:
            self.assertTrue(any(token in c for c in got), token)

    def test_t16_t18_download_lists(self):
        rep = self.q("SELECT attachments FROM reports WHERE slug='2025-annual-report' AND parent_slug IS NULL")[0]
        items = json.loads(rep["attachments"])
        self.assertEqual(len(items), T16_COUNT)
        titles = " | ".join((a.get("title") or "").lower() for a in items)
        for tok in T16_TITLES:
            self.assertIn(tok, titles)
        rep = self.q("SELECT attachments FROM reports WHERE slug='2026-senior-report' AND parent_slug IS NULL")[0]
        items = json.loads(rep["attachments"])
        self.assertEqual(len(items), T18_COUNT)
        titles = " | ".join((a.get("title") or "").lower() for a in items)
        self.assertIn(T18_MAPS, titles)

    def test_t17_overall_ranks(self):
        rows = self.q("SELECT state_code, rank FROM edition_measure_states WHERE edition_id=284 "
                      "AND measure_slug='Overall' AND state_code!='ALL' AND rank IS NOT NULL ORDER BY rank")
        self.assertEqual((rows[0]["state_code"], rows[0]["rank"]), ("NH", T17_FIRST[1]))
        self.assertEqual((rows[-1]["state_code"], rows[-1]["rank"]), ("LA", T17_LAST[1]))

    def test_t19_cancer_screenings_ca(self):
        r = self.q("SELECT value, rank FROM edition_measure_states WHERE state_code='CA' "
                   "AND edition_id=284 AND measure_slug='health_screenings_ahr'")[0]
        self.assertEqual((r["value"], r["rank"]), T19_CA_CS)

    def test_t23_definition_tokens(self):
        m = self.q("SELECT description FROM measures WHERE slug='health_screenings_ahr'")[0]
        for tok in T23_TOKENS:
            self.assertIn(tok, m["description"].lower())

    def test_t24_t26_category_anchors(self):
        rows = self.q("""SELECT m.display_name FROM measures m JOIN measure_categories c ON c.id=m.category_id
            WHERE c.name='Behavioral Health' ORDER BY m.display_name""")
        self.assertEqual(len(rows), T24_COUNT)
        names = " | ".join(r["display_name"].lower() for r in rows)
        for tok in T24_MEASURES:
            self.assertIn(tok, names)
        cat = self.q("""SELECT c.name FROM measures m JOIN measure_categories c ON c.id=m.category_id
            WHERE m.slug='Suicide_sr_c'""")[0]["name"]
        self.assertEqual(cat.lower(), T25_CATEGORY)
        rows = self.q("""SELECT m.display_name FROM measures m JOIN measure_categories c ON c.id=m.category_id
            WHERE c.name='Sleep Health' ORDER BY m.display_name""")
        self.assertEqual(" | ".join(r["display_name"].lower() for r in rows), " | ".join(T26_MEASURES))

    def test_t27_t28_t34_bookmark_sets(self):
        alice = self.q("SELECT id FROM users WHERE email=?", (ALICE,))[0]["id"]
        bob = self.q("SELECT id FROM users WHERE email=?", (BOB,))[0]["id"]
        carol = self.q("SELECT id FROM users WHERE email=?", (CAROL,))[0]["id"]
        alice_set = sorted(r["item_slug"] for r in self.q(
            "SELECT item_slug FROM bookmarks WHERE user_id=?", (alice,)))
        self.assertEqual(alice_set, ["Obesity", "mental_distress"])
        bob_set = sorted((r["kind"], r["item_slug"]) for r in self.q(
            "SELECT kind, item_slug FROM bookmarks WHERE user_id=?", (bob,)))
        self.assertEqual(bob_set, sorted([("measure", "Obesity"), ("measure", "mental_distress"),
                                          ("state", "CA")]))
        carol_set = sorted(r["item_slug"] for r in self.q(
            "SELECT item_slug FROM bookmarks WHERE user_id=?", (carol,)))
        self.assertEqual(carol_set, ["Obesity", "mental_distress"])

    def test_t29_t30_clean_tables(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM newsletter_signups")[0][0], 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM inquiries")[0][0], 0)

    def test_t31_t33_content_anchors(self):
        faq = self.q("SELECT answer_html FROM faq_items WHERE question LIKE '%updated%'")[0]["answer_html"].lower()
        for tok in T31_NAMES:
            self.assertIn(tok, faq)
        faq = self.q("SELECT answer_html FROM faq_items WHERE question LIKE '%guides%'")[0]["answer_html"].lower()
        self.assertIn(T32_WHO, faq)
        topic = self.q("SELECT description FROM topics WHERE title='Senior Health'")[0]["description"]
        for tok in T33_TOKENS:
            self.assertIn(tok, topic.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
