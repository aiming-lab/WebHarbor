"""Deterministic verifier contract tests for the CA.gov mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (phones, dates, counts,
    topics, sort anchors),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, homepage-only navigation) MUST FAIL,
  - a truncated run (no final done step) MUST FAIL,
  - a tampered run package (missing run dir, corrupt trajectory, 1x1 or
    missing screenshots, mutated after-DB) MUST FAIL,
  - task 9 state-mismatch: self-reported success with an unchanged DB MUST FAIL.

The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed (DB snapshots are taken from the frozen seed DB copy).
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
SEED = SITE / "instance_seed" / "california_gov.db"

sys.path.insert(0, str(VERIFY))
from grade import (  # noqa: E402
    BIRTH_CERT, CHRB_DEPT, DMV_DEPT, TAXES_COUNT, TAXES_MOST_RECENT,
    TAXES_NAMES, CALABLE_TOPICS, STATE_PARKS, STATE_BEACHES, LT_GOV,
    CDPH_LIST_NAME, DEATH_CERT, DMV_AUTO_CARDS, MOTOR_VEHICLES_DEPTS,
    SALES_TAX, SMOG_RESULTS, CALVET, POPULAR_SERVICES, BREA, CDPH_DEPT,
    DMV_AUTO_LICENSE_FILTER, DMV_AUTO_LICENSE_FILTER_COUNT,
    SMOG_STATION_TARGET, BIRTH_CERT_RELATED, MILESTONES, SPOTLIGHT, NAV,
    HORSE_LICENSE,
)

BASE = "http://localhost:40064"
SEED_COPY = None  # per-suite frozen copy of the seed DB


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


def tiny_png():
    """A 1x1 valid PNG — too small to be real page evidence."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000d49444154789c626001000000ffff030000060005"
        "57bfabd40000000049454e44ae426082")


# ---------------------------------------------------------------- run fixture
def write_run(root, urls, answer, shots=None, terminated=True, last_action="done",
              db_mutator=None, extra_steps=(), corrupt=False, missing_shots=False):
    """Materialize a run package in `root` (an empty temp dir)."""
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    steps = []
    for idx, url in enumerate(urls):
        before, after = f"step_{idx:03d}.png", f"step_{idx + 1:03d}.png"
        if shots != "tiny":
            (root / "screenshots" / before).write_bytes(make_png(1000 + idx))
            (root / "screenshots" / after).write_bytes(make_png(2000 + idx))
        elif idx == 0:
            (root / "screenshots" / before).write_bytes(tiny_png())
            (root / "screenshots" / after).write_bytes(tiny_png())
        steps.append({
            "step": idx, "url": url, "title": "CA.gov page",
            "page_text": "page", "thought": "navigate", "action": "goto",
            "params": {"url": url}, "observed_text": "page",
            "observed_text_before": "page",
            "screenshot_before": before, "screenshot_after": after,
        })
    idx = len(steps)
    final_before = f"step_{idx:03d}.png"
    if shots != "tiny":
        (root / "screenshots" / final_before).write_bytes(make_png(3000 + idx))
    else:
        (root / "screenshots" / final_before).write_bytes(tiny_png())
    steps.append({
        "step": idx, "url": urls[-1] if urls else BASE + "/", "title": "CA.gov page",
        "page_text": "page", "thought": "done", "action": last_action,
        "params": {"text": answer, "success": True}, "observed_text": "page",
        "observed_text_before": "page", "observed_text_after": "page",
        "screenshot_before": final_before, "screenshot_after": final_before,
    })
    steps.extend(dict(s, step=len(steps) + i) for i, s in enumerate(extra_steps))
    traj = {
        "task": "test", "task_id": "CA.gov--test", "start_url": BASE + "/",
        "model": "fixture", "max_steps": 40, "steps": steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else "max_steps",
        "final_answer": answer, "success_self_report": True,
        "final_url": urls[-1] if urls else BASE + "/",
    }
    text = json.dumps(traj, indent=1)
    if corrupt:
        text = text[:len(text) // 2]
    (root / "trajectory.json").write_text(text)
    shutil.copy2(SEED_COPY, root / "initial.db")
    shutil.copy2(SEED_COPY, root / "after.db")
    if db_mutator:
        db_mutator(root / "after.db")
    if missing_shots:
        shutil.rmtree(root / "screenshots")
    return root


def run_verifier(n, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{n}.py"), "--run_dir", str(run_dir), "--no_llm"],
        capture_output=True, text=True, timeout=120, cwd=str(VERIFY))
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": f"bad output: {proc.stdout[:120]} {proc.stderr[:120]}"}
    return verdict, proc


def urls_for(n):
    """Honest navigation URLs per task (the pages the task depends on)."""
    home = BASE + "/"
    out = [home]
    for kind, target, params in NAV[n]:
        if kind == "path":
            out.append(BASE + target)
        else:
            q = params.get("q", "").replace(" ", "+")
            out.append(f"{BASE}/search?q={q}")
    return out


# ------------------------------------------------------ honest answers (fixtures)
HONEST = {
    0: f"The birth certificate service page lists the phone number {BIRTH_CERT['phone']} and the page was last updated {BIRTH_CERT['date']}.",
    1: f"The California Horse Racing Board department page lists the main contact phone number {CHRB_DEPT['phone']} and the page shows Last updated {CHRB_DEPT['date']}.",
    2: "Yes. Yes, there are waiting lists for most levels of care; the wait for skilled nursing care may be prolonged for some homes, so the best way to assure future access to skilled nursing care is to enter the Home at a more independent level of care such as RCFE or DOM.",
    3: "The FAQ states the username requirements: Length: 6-20 characters. Allowed characters: Letters, numbers, and the following special characters: -_&%$#!*+= Spaces are not allowed Cannot contain profanity or inappropriate words Cannot be your email address",
    4: f"Filtering the All services directory by the topic Taxes shows {TAXES_COUNT} services, including: CalABLE disability savings account, Find business resources, Business permits and licensing help.",
    5: f"The CalABLE disability savings account service is tagged under the topics: {', '.join(CALABLE_TOPICS)}.",
    6: f"Among the Taxes services, {TAXES_MOST_RECENT[0]} has the most recent Last updated date: {TAXES_MOST_RECENT[1]}.",
    7: f"The Apply for a horse racing license service page lists the phone number {HORSE_LICENSE['phone']}, the page was last updated {HORSE_LICENSE['date']}, and the Contact button links to {HORSE_LICENSE['contact']}.",
    8: f"The DMV department page lists {DMV_DEPT['count']} services. The first service in the alphabetical list is {DMV_DEPT['first']} and the last is {DMV_DEPT['last']}.",
    9: "After submitting the feedback, the site shows the confirmation message: Thank you for your comments!.",
    10: "The three headlines in the In the spotlight section are: Governor Newsom signs most comprehensive data center laws in the nation, providing communities more control on water, electricity, and land use (September 21, 2026) | Governor Newsom proclaims state of emergency to bolster statewide El Nino preparedness, protect California (September 21, 2026) | Governor Newsom issues legislative update 9.20.2026 (September 20, 2026).",
    11: f"According to the California by the numbers section, California boasts {STATE_PARKS} state parks and {STATE_BEACHES} state beaches.",
    12: f"The Lieutenant Governor of California is {LT_GOV['name']}, and the link to their website is labeled \"Visit the Lt. Governor's website\".",
    13: f"On the Departments list page, the California Department of Public Health is listed under the inverted name \"{CDPH_LIST_NAME}\".",
    14: f"Apply for birth certificate is provided by {BIRTH_CERT['dept']} (last updated {BIRTH_CERT['date']}). Apply for death certificate is provided by {DEATH_CERT['dept']} (last updated {DEATH_CERT['date']}).",
    15: f"The four Popular related services cards on the DMV/Auto topic page are: {', '.join(DMV_AUTO_CARDS)}.",
    16: "The lead description reads: \"Get or renew your California driver's license, vehicle registration, and more. Learn about and obtain auto insurance. Resolve traffic tickets and keep your vehicle in shape with smog and repair services.\"",
    17: f"Searching the All departments page for \"motor vehicles\" returns two departments: {MOTOR_VEHICLES_DEPTS[0]} and {MOTOR_VEHICLES_DEPTS[1]}.",
    18: f"The Look up sales tax rates service is provided by {SALES_TAX['dept']}. The service page lists the phone number {SALES_TAX['phone']} and was last updated {SALES_TAX['date']}.",
    19: "According to the FAQs, Any person who is 16 years of age or older must possess a valid sport fishing license when taking any fish, shell fish, reptile, or amphibian in California. An annual license: Licenses are valid for a calendar year (January 1 through December 31) or for the remainder of the calendar year if purchased after January 1.",
    20: "The first item in the Do this first section is \"Check for alerts\": Emergency alerts will tell you how to stay safe. If you have a disability or access needs, evacuate early—getting help takes time.",
    21: "The search for smog returns 3 results: (1) Find an auto shop — a service provided by Bureau of Automotive Repair; (2) Repair or retire your vehicle — a service provided by Bureau of Automotive Repair; (3) DMV/Auto — a topic page.",
    22: f"The Frequently Asked Questions section contains {CALVET['faq_count']} questions. About credit scores: Yes. We have credit standards, but we do not have a minimum credit score requirement. We manually underwrite all our home loans to maximize flexibility and improve your homeownership opportunities.",
    23: f"The six quick-link labels in the Popular services band are: {', '.join(POPULAR_SERVICES)}.",
    24: f"The Bureau of Real Estate Appraisers department page lists the contact phone number {BREA['phone']} and shows Last updated {BREA['date']}.",
    25: f"The Apply for birth certificate service page lists the phone number {BIRTH_CERT['phone']}. The California Department of Public Health department page lists the phone number {CDPH_DEPT['phone']}. The two numbers are not the same.",
    26: f"Filtering the DMV/Auto topic page service list by \"license\" leaves {DMV_AUTO_LICENSE_FILTER_COUNT} services: {', '.join(DMV_AUTO_LICENSE_FILTER)}.",
    27: f"The \"Find a smog station\" card leads to the service page named \"{SMOG_STATION_TARGET['name']}\". Its description says: {SMOG_STATION_TARGET['desc']}, Smog Check stations, and vehicle safety systems inspection stations near you. The page lists the phone number {SMOG_STATION_TARGET['phone']}.",
    28: f"Related services listed on the Apply for birth certificate page include: {', '.join(BIRTH_CERT_RELATED[:4])}.",
    29: "The California milestones section shows: 1.5m zero emission vehicles in the state (by 2025); 90% clean energy by 2035; 230+ state government agencies serving you; $60b+ generated to support our communities.",
}

# A wrong answer: plausible-looking but off by the key fact per task.

# Expanded reviewer tasks retain the independent component fixture expectations.
_ORIGINAL_HONEST = HONEST.copy()
_REVIEW_COMPONENTS = json.loads((VERIFY / "review_components.json").read_text())

_original_urls_for = urls_for
def urls_for(n):
    return list(dict.fromkeys(url for k in _REVIEW_COMPONENTS.get(str(n), [n]) for url in _original_urls_for(k)))
for _n, _parts in _REVIEW_COMPONENTS.items():
    HONEST[int(_n)] = "\n".join(_ORIGINAL_HONEST[k] for k in _parts)

WRONG = {n: HONEST[n].replace(BIRTH_CERT["phone"], "916-999-9999") if n in (0, 25) else
         HONEST[n].replace(CHRB_DEPT["date"], "01/01/2030") if n == 1 else
         "The answer is 42." for n in HONEST}


def feedback_mutator(path, helpful="no", comments="The refund status link was hard to find",
                      page_path="http://localhost:40064/departments/236/"):
    def mutate(db_path):
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO feedback (page_path, helpful, comments, created_at) VALUES (?,?,?,?)",
            (page_path, helpful, comments, "2026-09-22 12:00:00.000000"))
        con.commit()
        con.close()
    return mutate


def mutate_readonly(db_path):
    con = sqlite3.connect(db_path)
    con.execute("UPDATE departments SET phone = '000-000-0000' WHERE id = 220")
    con.commit()
    con.close()


class ContractSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SEED.is_file():
            raise unittest.SkipTest(
                f"seed DB not materialized yet: {SEED} (run the site container once)")
        global SEED_COPY
        SEED_COPY = Path(tempfile.mkdtemp(prefix="wh-cagov-seed-")) / "seed.db"
        shutil.copy2(SEED, SEED_COPY)
        cls.seed_copy = SEED_COPY

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(SEED_COPY.parent, ignore_errors=True)

    def tmp(self):
        d = Path(tempfile.mkdtemp(prefix="wh-cagov-run-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    # ------------------------------------------------ ground-truth sanity
    def q(self, sql, params=()):
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, params)]
        finally:
            con.close()

    def test_seed_facts(self):
        rows = self.q("SELECT * FROM services WHERE id=52")
        self.assertEqual(rows[0]["phone"], BIRTH_CERT["phone"])
        self.assertEqual(rows[0]["last_updated"], BIRTH_CERT["date"])
        self.assertEqual(rows[0]["department_id"], 176)
        self.q("SELECT * FROM departments WHERE id=185")[0]["phone"] == CHRB_DEPT["phone"]
        self.assertEqual(
            self.q("SELECT * FROM departments WHERE id=185")[0]["last_updated"], CHRB_DEPT["date"])
        horse = self.q("SELECT * FROM services WHERE id=1144")[0]
        self.assertEqual(horse["phone"], HORSE_LICENSE["phone"])
        self.assertEqual(horse["contact_url"], HORSE_LICENSE["contact"])
        dmv = self.q("SELECT name FROM services WHERE department_id=220 ORDER BY dept_rank")
        self.assertEqual(len(dmv), DMV_DEPT["count"])
        self.assertEqual(dmv[0]["name"], DMV_DEPT["first"])
        self.assertEqual(dmv[-1]["name"], DMV_DEPT["last"])
        taxes = self.q(
            "SELECT s.name, s.last_updated FROM services s JOIN service_topics st ON st.service_id=s.id "
            "JOIN topics t ON t.id=st.topic_id WHERE t.name='Taxes'")
        self.assertEqual(len(taxes), TAXES_COUNT)
        apos = str.maketrans({chr(0x2019): "'", chr(0x2018): "'"})

        def plain(s):
            return s.translate(apos)
        self.assertEqual({plain(r["name"]) for r in taxes}, TAXES_NAMES)
        newest = max(taxes, key=lambda r: r["last_updated"])
        self.assertEqual((newest["name"], newest["last_updated"]), TAXES_MOST_RECENT)
        calable = self.q(
            "SELECT t.name FROM topics t JOIN service_topics st ON st.topic_id=t.id "
            "WHERE st.service_id=1182 ORDER BY st.position")
        self.assertEqual([r["name"] for r in calable], CALABLE_TOPICS)
        self.assertEqual(
            self.q("SELECT list_name FROM departments WHERE id=176")[0]["list_name"],
            CDPH_LIST_NAME)
        self.assertEqual(self.q("SELECT phone FROM departments WHERE id=300")[0]["phone"],
                         BREA["phone"])
        self.assertEqual(self.q("SELECT phone FROM departments WHERE id=176")[0]["phone"],
                         CDPH_DEPT["phone"])
        faqs = self.q("SELECT COUNT(*) AS n FROM faqs WHERE service_id=64")
        self.assertEqual(faqs[0]["n"], CALVET["faq_count"])
        stats = self.q("SELECT description FROM homepage_stats WHERE position=3")[0]["description"]
        self.assertIn(f"{STATE_PARKS} state parks and {STATE_BEACHES} state beaches", stats)
        ltgov = self.q("SELECT * FROM officials WHERE role='Lieutenant Governor'")[0]
        self.assertEqual(plain(ltgov["name"]), LT_GOV["name"])
        self.assertEqual(plain(ltgov["link_label"]), LT_GOV["label"])
        news = self.q("SELECT title, display_date FROM news_items ORDER BY position")
        self.assertEqual(len(news), 3)
        for item, (frag, d) in zip(news, SPOTLIGHT):
            self.assertIn(frag, item["title"])
            self.assertEqual(item["display_date"], d)
        dmv_auto_names = {plain(r["name"]) for r in self.q(
            "SELECT s.name FROM services s JOIN service_topics st ON st.service_id=s.id "
            "JOIN topics t ON t.id=st.topic_id WHERE t.slug='dmv-auto'")}
        for name in DMV_AUTO_LICENSE_FILTER:
            self.assertIn(name, dmv_auto_names, name)
        smog_shop = self.q("SELECT * FROM services WHERE id=6")[0]
        self.assertEqual(smog_shop["name"], SMOG_STATION_TARGET["name"])
        self.assertEqual(smog_shop["phone"], SMOG_STATION_TARGET["phone"])
        self.assertEqual(self.q("SELECT COUNT(*) AS n FROM feedback")[0]["n"], 0)

    def test_tasks_registry(self):
        tasks = [json.loads(l) for l in (SITE / "tasks.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(len(tasks), 30)
        for row in tasks:
            self.assertIn(row["verifier_path"], {f"sites/california_gov/verify/verify_{n}.py" for n in range(30)})
            self.assertIn("FACT CHECKPOINTS", row["judge_rubric"])
            self.assertIn("MUST", row["judge_rubric"])
            self.assertNotIn("answer", row)

    # ------------------------------------------------ per-task honest / adversarial
    def _assert(self, n, run_dir, should_pass, note):
        verdict, proc = run_verifier(n, run_dir)
        self.assertEqual(verdict.get("pass"), should_pass,
                         f"task {n} {note}: expected {should_pass}, got {verdict} "
                         f"(exit {proc.returncode})")
        self.assertEqual(proc.returncode, 0 if should_pass else 1)
        return verdict

    def test_honest_runs_pass(self):
        for n in range(30):
            with self.subTest(task=n):
                d = self.tmp()
                mutator = feedback_mutator(None) if n == 9 else None
                if n == 9:
                    root = write_run(d, urls_for(n), HONEST[n],
                                     db_mutator=feedback_mutator(None))
                else:
                    root = write_run(d, urls_for(n), HONEST[n])
                self._assert(n, root, True, "honest")

    def test_noop_runs_fail(self):
        for n in range(30):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, [BASE + "/"], "")
                self._assert(n, root, False, "no-op")

    def test_wrong_answers_fail(self):
        for n in range(30):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), WRONG[n],
                                 db_mutator=feedback_mutator(None) if n == 9 else None)
                self._assert(n, root, False, "wrong answer")

    def test_shortcut_runs_fail(self):
        """Correct answer with homepage-only navigation = knowledge shortcut."""
        for n in range(30):
            if n in (10, 11, 12, 23):  # homepage tasks: home IS the required page
                continue
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, [BASE + "/"], HONEST[n],
                                 db_mutator=feedback_mutator(None) if n == 9 else None)
                verdict = self._assert(n, root, False, "shortcut")
                self.assertIn(verdict.get("reason"), ("nav_required_pages", "shot_target_page"))

    def test_truncated_runs_fail(self):
        for n in range(30):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), HONEST[n], last_action="goto",
                                 db_mutator=feedback_mutator(None) if n == 9 else None)
                self._assert(n, root, False, "truncated")

    def test_tiny_screenshots_fail(self):
        for n in (0, 9, 21):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), HONEST[n], shots="tiny",
                                 db_mutator=feedback_mutator(None) if n == 9 else None)
                verdict = self._assert(n, root, False, "tiny screenshots")
                self.assertIn("shot", verdict.get("reason", ""))

    def test_missing_screenshots_fail(self):
        for n in (0, 21):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), HONEST[n], missing_shots=True)
                self._assert(n, root, False, "missing screenshots")

    def test_corrupt_trajectory_fails(self):
        for n in (0, 9):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), HONEST[n], corrupt=True)
                verdict = self._assert(n, root, False, "corrupt trajectory")
                self.assertEqual(verdict.get("reason"), "run_dir_unreadable")

    def test_missing_run_dir_fails(self):
        for n in (0, 15):
            with self.subTest(task=n):
                d = self.tmp() / "does-not-exist"
                verdict, proc = run_verifier(n, d)
                self.assertFalse(verdict.get("pass"))
                self.assertEqual(proc.returncode, 1)

    def test_readonly_mutation_fails(self):
        for n in (0, 4, 17, 26):
            with self.subTest(task=n):
                d = self.tmp()
                root = write_run(d, urls_for(n), HONEST[n], db_mutator=mutate_readonly)
                verdict = self._assert(n, root, False, "mutated after-DB")
                self.assertEqual(verdict.get("reason"), "db_read_only_unchanged")

    def test_task9_state_mismatch_fails(self):
        """Self-reported success but the DB unchanged: MUST FAIL."""
        d = self.tmp()
        root = write_run(d, urls_for(9), HONEST[9])  # no feedback row written
        verdict = self._assert(9, root, False, "state mismatch")
        self.assertEqual(verdict.get("reason"), "db_feedback_row")

    def test_task9_wrong_row_fails(self):
        for kwargs in (
            {"helpful": "yes"},
            {"comments": "Great site"},
            {"page_path": "http://localhost:40064/departments/220/"},
        ):
            with self.subTest(**kwargs):
                d = self.tmp()
                root = write_run(d, urls_for(9), HONEST[9],
                                 db_mutator=feedback_mutator(None, **kwargs))
                self._assert(9, root, False, "wrong feedback row")

    def test_task9_double_submit_fails(self):
        def double(db_path):
            feedback_mutator(None)(db_path)
            feedback_mutator(None)(db_path)
        d = self.tmp()
        root = write_run(d, urls_for(9), HONEST[9], db_mutator=double)
        self._assert(9, root, False, "two feedback rows")

    def test_offsite_navigation_fails(self):
        d = self.tmp()
        urls = [BASE + "/", "https://www.ca.gov/departments/176/services/52/"]
        root = write_run(d, urls, HONEST[0])
        verdict = self._assert(0, root, False, "offsite shortcut")
        self.assertEqual(verdict.get("reason"), "nav_origin_local")


if __name__ == "__main__":
    unittest.main()
