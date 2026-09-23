#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Apple verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact navigation shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's Playwright audit of
the running wh-ver-apple container), and the adversarial cases prove the
verifiers reject no-op runs, recall shortcuts, wrong answers, foreign task ids,
broken run packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because the
repository tracks no instance assets; set WH_CONTAINER to point at the site's
container when it is not the default wh-ver-apple.
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
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
REPO_DIR = SITE_DIR.parent.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://127.0.0.1:41002"
TASKS = list(range(43))

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)

# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/mac"],
        "The latest MacBook Air models are the MacBook Air 13\" at $1,099.00 and the "
        "MacBook Air 15\" at $1,299.00."),
    1: (["/support/article/ios-17-new-features"],
        "iOS 17 adds StandBy, NameDrop, Contact Posters, and Live Voicemail. It is "
        "compatible with the iPhone 12 — the compatible-devices list includes the "
        "iPhone 12, iPhone 12 mini, iPhone 12 Pro, and iPhone 12 Pro Max."),
    2: (["/product/iphone-14-pro", "/product/iphone-15-pro"],
        "The iPhone 14 Pro costs $999.00 with the A16 Bionic chip; the iPhone 15 Pro "
        "also costs $999.00 but with the A17 Pro chip."),
    3: (["/product/iphone-17-pro", "/product/iphone-17-pro-max"],
        "The latest iPhones are the iPhone 17 Pro at $1,099.00 with a 6.3-inch display "
        "and the iPhone 17 Pro Max at $1,199.00 with a 6.9-inch display."),
    4: (["/product/macbook-pro-16-inch-m3-max"],
        "The MacBook Pro 16-inch with the M3 Max chip (16-core CPU, 40-core GPU, 64GB "
        "unified memory, 1TB SSD) costs $4299.00."),
    5: (["/product/iphone-17-pro"],
        "The latest iPhone is the iPhone 17 Pro at $1099.00; its spec page lists "
        "Release year 2024 and no exact release date."),
    6: (["/airpods"],
        "Apple currently offers 7 types of AirPods: AirPods Pro 3, AirPods Max 2, "
        "AirPods 4, AirPods 3rd generation (Lightning), AirPods 3rd generation "
        "(MagSafe), AirPods Pro (2nd generation), and AirPods (2nd generation)."),
    7: (["/vision-pro"],
        "The Apple Vision Pro was released on February 2, 2024 in the United States."),
    8: (["/product/ipad-pro-m5"],
        "The latest iPad is the iPad Pro M5: M5 chip, 11\" or 13\" Ultra Retina XDR "
        "display, storage options 256GB, 512GB, 1TB, 2TB, From $999."),
    9: (["/store/pickup?product=iphone-17-pro&zip=90038&store=Apple+The+Grove&date=2024-01-10"],
        "The iPhone 17 Pro is in stock for pickup. I scheduled an in-store pickup at "
        "Apple The Grove (0.8 miles, the nearest store) on January 10, 2024; the page "
        "confirms the pickup is scheduled and available."),
    10: (["/product/macbook-air-13"],
         "The latest MacBook is the MacBook Air 13\" with the M5 chip, 16GB of memory, "
         "and 256GB or 512GB of storage (From $1099)."),
    11: (["/product/ipad-pro-m5"],
         "The latest iPad released is the iPad Pro M5: released October 15, 2025, with "
         "256GB base storage and a starting price of $999."),
    12: (["/support/repair"],
         "Apple Repair options on the site include Mail-in repair and Carry-in repair "
         "(plus Onsite repair for business customers and Express Replacement Service)."),
    13: (["/product/macbook-air-13"],
         "The MacBook Air comes in 4 colors: Midnight, Starlight, Space Gray, and Silver."),
    14: (["/configure/macbook-pro-14-inch-m3"],
         "The MacBook Pro 14-inch with the M3 chip starts at $1599. Upgrade options: "
         "memory 16GB +$200 or 24GB +$400, storage 1TB +$200, software Final Cut Pro "
         "+$299.99 or Logic Pro +$199.99. The maximum upgrade without pre-installed "
         "software is 24GB memory + 1TB storage = a $600 total price difference."),
    15: (["/configure/macbook-pro-14-inch-m3"],
         "When customizing the 14-inch MacBook Pro there are 4 keyboard layouts "
         "available: US English, British English, Spanish, and French."),
    16: (["/product/airpods-3-lightning", "/product/airpods-3-magsafe"],
         "There are 2 types of AirPods 3rd generation: the Lightning model at $169 and "
         "the MagSafe model at $179 — a $10 price difference."),
    17: (["/store/pickup?product=smart-folio-for-ipad-pro-13-inch-m4&zip=90038"],
         "For zip code 90038 the closest store is Apple The Grove at 0.8 miles; the "
         "Smart Folio for iPad Pro 13-inch (M4) is available for pickup there today."),
    18: (["/support/article/iphone-trade-in-offers"],
         "Yes, trade-in offers are available for the latest iPhone — you can get up to "
         "$750 in credit toward a new iPhone."),
    19: (["/mac"],
         "Mac: \"If you can dream it, Mac can do it.\" MacBook Pro: \"The Pro "
         "laptop, reimagined.\""),
    20: (["/product/iphone-14-plus"],
         "An iPhone 14 Plus with 256GB storage in Purple costs $989.00 ($899 plus the "
         "$90 storage upgrade)."),
    21: (["/product/ipad-pro-m5"],
         "The latest iPad Pro storage options are 256GB, 512GB, 1TB, and 2TB."),
    22: (["/trade-in/iphone-13-pro-max"],
         "The iPhone 13 Pro Max in good condition trades in for up to $440."),
    23: (["/watch"],
         "The Apple Watch Series 11 starts at $399 and the Apple Watch SE at $249 — a "
         "$150 price difference."),
    24: (["/product/imac-24"],
         "The most recent iMac starts at $1299.00."),
    25: (["/product/apple-tv-4k"],
         "The Apple TV 4K is powered by the A15 Bionic processor."),
    26: (["/product/ipad-mini"],
         "The latest iPad mini supports 4K video recording (at up to 60 fps) — its "
         "maximum video recording resolution is 4K."),
    27: (["/product/homepod-mini"],
         "Yes — the HomePod mini is available in multiple colors: White, Yellow, "
         "Orange, Blue, and Space Gray."),
    28: (["/product/mac-mini-m2-pro"],
         "Yes, the Mac mini can be configured with a GPU larger than 16-core — it is "
         "configurable up to a 19-core GPU."),
    29: (["/product/macbook-air-13-inch-m3"],
         "The MacBook Air's estimated battery life during web browsing is up to 15 "
         "hours of wireless web browsing per its Tech Specs."),
    30: (["/product/ipad-pro-m5"],
         "The latest iPad Pro models come in 256GB, 512GB, 1TB, and 2TB: the iPad Pro "
         "M5 starts at $999, with 512GB +$200, 1TB +$400, and 2TB +$530."),
    31: (["/product/apple-watch-series-11"],
         "The slogan for the latest Apple Watch Series (Series 11) is \"The ultimate "
         "way to watch your health.\""),
    32: (["/trade-in/iphone-11-pro-max"],
         "The iPhone 11 Pro Max trades in for up to $230 in good condition."),
    33: (["/product/imac-24"],
         "The newest iMac is available in 7 colors: Blue, Green, Pink, Silver, "
         "Yellow, Orange, and Purple."),
    34: (["/product/apple-tv-4k"],
         "The Apple TV 4K weighs 208 grams (Wi-Fi), 214 grams (Wi-Fi + Ethernet), and "
         "measures 93 x 93 x 31 mm. Siri Remote features: touch-enabled clickpad, "
         "Find My, USB-C charging, plus Power and Mute buttons and Siri."),
    35: (["/accessories"],
         "There are 4 types of Apple Pencil: Apple Pencil Pro, Apple Pencil (2nd "
         "generation), Apple Pencil (USB-C), and Apple Pencil (1st generation). The "
         "Apple Pencil Pro and the 2nd generation support wireless pairing and "
         "wireless charging."),
    36: (["/music"],
         "The Apple Music page features these singers: Taylor Swift, Drake, The "
         "Weeknd, Billie Eilish, Dua Lipa, Olivia Rodrigo, Bad Bunny, and Harry Styles."),
    37: (["/product/iphone-13-pro", "/product/iphone-14-pro", "/product/iphone-15-pro"],
         "iPhone 13 Pro colors: Sierra Blue, Alpine Green, Graphite, Gold, Silver. "
         "iPhone 14 Pro: Deep Purple, Space Black, Gold, Silver. iPhone 15 Pro: "
         "Natural Titanium, Blue Titanium, White Titanium, Black Titanium."),
    38: (["/vision-pro"],
         "Apple Vision Pro accessories include the Travel Case ($199), the Battery "
         "Pack ($199), and the Light Seal ($199)."),
    39: (["/support/apple-id-forgot-password"],
         "If you forgot your Apple ID password, reset it on the web at iforgot.apple.com, "
         "or on your iPhone via Settings > [your name] > Sign-In & Security > Change "
         "Password."),
    40: (["/vision-pro"],
         "The Apple Vision Pro weighs 600 to 650 grams depending on the Light Seal and "
         "band. Built-in apps include Safari, Photos, Music, Messages, Apple TV, "
         "FaceTime, Notes, Mail, Keynote, and Freeform."),
    41: (["/product/ipad-mini-64gb-wi-fi-cellular"],
         "An iPad mini with 64GB storage and Wi-Fi + Cellular connectivity costs $649."),
    42: (["/support/article/apple-watch-series-7-8-9-updates"],
         "Apple Watch Series 7, 8, and 9 all support the watchOS 10 update; to update, "
         "open the Watch app on iPhone > My Watch > General > Software Update."),
}

# task -> plausible-but-wrong answer (contradicts the mirror ground truth)
WRONG = {
    0: "The MacBook Air models cost $999 and $1199.",
    1: "iOS 17 adds a redesigned Control Center and RCS support; the iPhone 12 is not compatible.",
    2: "The iPhone 14 Pro is $999 with the A15 Bionic; the iPhone 15 Pro is $1099 with the A18 Pro.",
    3: "The iPhone 17 Pro is $1099 with a 6.1-inch display and the Pro Max is $1299 with a 6.7-inch display.",
    4: "It costs $3499.00.",
    5: "The latest iPhone is the iPhone 15 Pro, released September 22, 2023, at $999.",
    6: "There are 5 types of AirPods available.",
    7: "The Apple Vision Pro was released on March 15, 2024 in Canada.",
    8: "The latest iPad is the iPad Pro M5 with an M5 chip, a Liquid Retina display, and 64GB/128GB storage.",
    9: "I scheduled a pickup at Apple Century City on January 12, 2024.",
    10: "The latest MacBook is the MacBook Air 13\" with an M4 chip, 8GB of memory, and 256GB storage.",
    11: "The latest iPad was released June 1, 2024 with 64GB base storage at $799.",
    12: "Apple offers express shipping and phone support.",
    13: "The MacBook Air comes in 5 colors.",
    14: "The maximum upgrade adds $800 to the base price.",
    15: "There are 6 keyboard types available.",
    16: "There are 3 types of AirPods 3rd generation with a $20 price difference.",
    17: "The closest store is Apple Beverly Center at 1.5 miles, but the Smart Folio is out of stock.",
    18: "No, there are no trade-in offers for the latest iPhone.",
    19: "The Mac slogan is 'Think different' and the MacBook Pro slogan is 'Speed. Beauty.'",
    20: "The iPhone 14 Plus 256GB in Purple costs $799.",
    21: "The iPad Pro storage options are 64GB, 128GB, 256GB, and 512GB.",
    22: "The iPhone 13 Pro Max trades in for up to $500.",
    23: "The price difference between the two watches is $100.",
    24: "The most recent iMac starts at $1499.",
    25: "The Apple TV 4K uses an A12X Bionic processor.",
    26: "The latest iPad mini records at a maximum of 1080p.",
    27: "The HomePod mini only comes in White.",
    28: "No, the Mac mini maxes out at a 16-core GPU.",
    29: "The MacBook Air lasts up to 18 hours of web browsing.",
    30: "The iPad Pro storage options are 128GB, 256GB, 512GB, and 1TB.",
    31: "The Apple Watch Series 11 slogan is 'Smarter. Brighter. Mightier.'",
    32: "The iPhone 11 Pro Max trades in for up to $180.",
    33: "The newest iMac is available in 5 colors.",
    34: "The Apple TV 4K weighs 425 grams and measures 98 x 98 x 35 mm; the Siri Remote has a touchpad and a headphone jack.",
    35: "There are 3 types of Apple Pencil and the USB-C one supports wireless charging.",
    36: "The Apple Music page features Ed Sheeran, Adele, and Beyoncé.",
    37: "iPhone 13 Pro: Pacific Blue; iPhone 14 Pro: Lavender; iPhone 15 Pro: Rose Gold.",
    38: "The Apple Vision Pro accessories page shows the AirTag and the Magic Keyboard.",
    39: "Call 1-800-MY-APPLE to reset your password.",
    40: "The Vision Pro weighs 450 grams and its built-in apps are Calendar, Clock, Weather, Stocks, and Home.",
    41: "The iPad mini 64GB Wi-Fi + Cellular costs $599.",
    42: "Apple Watch Series 7, 8, and 9 all run watchOS 11.",
}


def make_run(root: Path, task: int, paths, answer, task_id=None,
             drop_trajectory=False, break_screenshot=False):
    run = root / f"run_{task}"
    (run / "screenshots").mkdir(parents=True)
    (run / "screenshots" / "step_000.png").write_bytes(PNG_1PX)
    (run / "screenshots" / "step_001.png").write_bytes(PNG_1PX)
    steps = []
    for i, p in enumerate(paths):
        shot = "step_000.png" if i % 2 == 0 else "step_001.png"
        steps.append({
            "step": i, "url": ORIGIN + p, "url_after": ORIGIN + p,
            "title": "Apple", "thought": "browse", "action": "navigate",
            "params": {"url": ORIGIN + p},
            "screenshot_before": shot, "screenshot_after": shot,
        })
    if break_screenshot:
        steps[-1]["screenshot_after"] = "step_999.png"
    trajectory = {
        "task_id": task_id or f"Apple--{task}",
        "task": f"Apple task {task}",
        "start_url": ORIGIN + "/",
        "model": "gpt-5.6-sol",
        "max_steps": 15,
        "steps": steps,
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "judge_rubric": "",
        "verifier_path": f"sites/apple/verify/verify_{task}.py",
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
            os.environ.get("WH_CONTAINER", "wh-ver-apple"), "instance_seed")
    db = tmp / "seed_copy.db"
    shutil.copy2(SEED_DB, db)
    return db


class VerifierTests(unittest.TestCase):
    def execute(self, task, *, answer=None, paths=None, task_id=None,
                drop_trajectory=False, break_screenshot=False, mutate=None,
                empty_steps=False):
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
            if empty_steps:
                traj = json.loads((run / "trajectory.json").read_text())
                traj["steps"] = []
                (run / "trajectory.json").write_text(json.dumps(traj))
            return run_verifier(task, run, initial, after)

    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task)
                self.assertTrue(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 0)

    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"], answer="")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)
                self.assertEqual(result["reason"], "final_answer_nonempty")

    def test_shortcut_correct_answer_without_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, paths=["/"])
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)

    def test_wrong_answer_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, answer=WRONG[task])
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)

    def test_partial_navigation_fails(self):
        # task 2 requires BOTH product pages; dropping one must fail on nav
        result = self.execute(2, paths=["/product/iphone-14-pro"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_both_product_pages")
        # task 37 requires all three product pages
        result = self.execute(37, paths=["/product/iphone-13-pro", "/product/iphone-14-pro"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_all_three_pages")
        # task 9 requires the pickup URL to carry the nearest store and the date
        result = self.execute(9, paths=[
            "/store/pickup?product=iphone-17-pro&zip=90038&store=Apple+Beverly+Center&date=2024-01-10"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_pickup_nearest_store")
        result = self.execute(9, paths=[
            "/store/pickup?product=iphone-17-pro&zip=90038&store=Apple+The+Grove&date=2024-01-12"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_pickup_jan10_2024")
        result = self.execute(9, paths=[
            "/store/pickup?product=iphone-15-pro&zip=90038&store=Apple+The+Grove&date=2024-01-10"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_pickup_latest_iphone")
        # task 17 requires zip=90038 on the pickup URL
        result = self.execute(17, paths=[
            "/store/pickup?product=smart-folio-for-ipad-pro-13-inch-m4"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "nav_pickup_zip_90038")

    def test_foreign_task_id_fails(self):
        result = self.execute(0, task_id="Apple--42")
        self.assertFalse(result["pass"])
        self.assertEqual(result["returncode"], 1)

    def test_missing_trajectory_fails(self):
        result = self.execute(0, drop_trajectory=True)
        self.assertFalse(result["pass"])
        self.assertEqual(result["returncode"], 1)

    def test_missing_referenced_screenshot_fails(self):
        result = self.execute(0, break_screenshot=True)
        self.assertFalse(result["pass"])
        self.assertEqual(result["returncode"], 1)

    def test_empty_steps_fails(self):
        result = self.execute(0, empty_steps=True)
        self.assertFalse(result["pass"])
        self.assertEqual(result["returncode"], 1)

    def test_task29_honest_current_air_reading_passes(self):
        # (b) reading: the current Air's Tech Specs battery + explicit absence
        # statement — the honest report for the latest model on the mirror.
        result = self.execute(
            29, paths=["/product/macbook-air-13"],
            answer="The MacBook Air 13-inch (M5) Technical Specifications list "
                   "battery life as up to 18 hours; the page does not specify a "
                   "web-browsing figure.")
        self.assertTrue(result["pass"], result)

    def test_task29_15h_claim_without_web_page_fails(self):
        # a 15-hour claim must be backed by the page that actually carries it
        result = self.execute(
            29, paths=["/product/macbook-air-13"],
            answer="The MacBook Air lasts up to 15 hours during web browsing.")
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "answer_battery_web_browsing")

    def test_task29_bare_18h_claim_fails(self):
        # claiming 18 hours IS the web-browsing figure contradicts the mirror
        result = self.execute(
            29, paths=["/product/macbook-air-13"],
            answer="The MacBook Air lasts up to 18 hours of web browsing.")
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "answer_battery_web_browsing")

    def test_db_write_fails_state_check(self):
        def add_user(connection):
            connection.execute(
                "INSERT INTO user (first_name, last_name, email, password_hash) "
                "VALUES ('Eve', 'Attacker', 'eve@x.com', 'x')")
        result = self.execute(4, mutate=add_user)
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "db_state")

    def test_db_cart_write_fails_state_check(self):
        def add_cart_row(connection):
            pid = connection.execute("SELECT id FROM product LIMIT 1").fetchone()[0]
            uid = connection.execute("SELECT id FROM user LIMIT 1").fetchone()[0]
            connection.execute(
                "INSERT INTO cart_item (user_id, product_id, quantity, color, storage) "
                "VALUES (?, ?, 1, '', '')", (uid, pid))
        result = self.execute(6, mutate=add_cart_row)
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "db_state")

    def test_verifier_fetches_db_from_container(self):
        # one task graded exactly the way eval_judge runs it (no explicit DBs):
        # the verifier docker-cps instance_seed + instance from WH_CONTAINER
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = make_run(root, 4, POSITIVE[4][0], POSITIVE[4][1])
            env = dict(os.environ)
            env.setdefault("WH_CONTAINER", "wh-ver-apple")
            r = subprocess.run(
                [sys.executable, str(VERIFY_DIR / "verify_4.py"),
                 "--run_dir", str(run), "--no_llm", "True"],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            verdict = json.loads(r.stdout)
            self.assertTrue(verdict["pass"], verdict)


class TaskFileContractTests(unittest.TestCase):
    TASKS_FILE = REPO_DIR / "sites" / "apple" / "tasks.jsonl"
    ORIG_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]

    def test_rows_and_keys(self):
        lines = [l for l in self.TASKS_FILE.read_text().splitlines() if l.strip()]
        self.assertEqual(len(lines), 43)
        for i, line in enumerate(lines):
            with self.subTest(row=i):
                row = json.loads(line)
                self.assertEqual(list(row.keys()),
                                 self.ORIG_KEYS + ["verifier_path", "judge_rubric"],
                                 f"keys must be the five originals + verifier_path "
                                 f"+ judge_rubric, got {list(row.keys())}")
                self.assertNotIn("answer", row)
                self.assertEqual(row["id"], f"Apple--{i}")
                self.assertEqual(row["verifier_path"], f"sites/apple/verify/verify_{i}.py")
                self.assertTrue((REPO_DIR / row["verifier_path"]).exists(),
                                 f"missing verifier {row['verifier_path']}")
                self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."),
                                f"rubric must start with FACT CHECKPOINTS.")
                self.assertGreater(len(row["judge_rubric"]), 80)


if __name__ == "__main__":
    unittest.main()
