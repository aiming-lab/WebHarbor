#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Amazon verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact trajectory shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's Playwright audit of
the running container), and the adversarial cases prove the verifiers reject
no-op runs, recall shortcuts, wrong answers, foreign task ids, broken run
packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because the
repository tracks no instance assets; set WH_CONTAINER to point at the site's
container when it is not the default wh-ver-amazon.
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

ORIGIN = "http://127.0.0.1:41001"
TASKS = list(range(41))

# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/search?q=xbox+wireless+controller&color=green&min_rating=4",
         "/product/xbox-wireless-controller-velocity-green"],
        "The qualifying controller is the Xbox Wireless Controller in Velocity Green. "
        "It costs $64.99, is rated 4.7 stars with 28,430 reviews, and includes Bluetooth, "
        "a textured grip, and a hybrid D-pad. This is the only green Xbox wireless "
        "controller rated above 4 stars; the Mineral Camo Green variant is rated 3.8."),
    1: (["/search?q=womens+golf+polo&size=m&min_price=50&max_price=75&sort=price_asc",
         "/product/women-s-izod-swingflex-golf-polo"],
        "The lowest-priced qualifying polo is the Women's IZOD SwingFlex Golf Polo at "
        "$52.00 (size M available, 4.4 stars). The other qualifying size-M polos between "
        "$50 and $75 are the Women's Classic Pique Golf Polo at $55.00 and the Women's "
        "Under Armour Playoff Golf Polo at $69.99."),
    2: (["/search?q=gaming+desktop", "/product/hp-omen-25l-gaming-desktop"],
        "The HP OMEN 25L Gaming Desktop matches: it runs Windows 11 Home with a 1TB SSD "
        "and costs $1,299.99 (4.5 stars, 1,943 reviews). The MSI Aegis RS Gaming Desktop "
        "is the other Windows 11 Home machine with a 1TB NVMe SSD at $1,649.99."),
    3: (["/search?q=climbing+gear&sort=price_desc"],
        "Sorted by price high to low, the first 3 results are: "
        "1) Mammut 9.5 Crag Classic Climbing Rope 60m - $219.95, "
        "2) Evolv Shaman Climbing Shoes - $179.00, "
        "3) Petzl GriGri Plus Belay Device - $149.95."),
    4: (["/search?q=nintendo+switch+lite&condition=Used+-+Good&sort=price_asc",
         "/product/nintendo-switch-lite-gray"],
        "The cheapest 'Used - Good' Nintendo Switch Lite is the Gray one at $149.99 "
        "(4.7 stars, 4,547 reviews). The other Used - Good units are the Yellow at "
        "$159.99 and the Blue at $164.99."),
    5: (["/search?q=iphone+12+pro&color=blue", "/product/apple-iphone-12-pro-128gb", "/bag"],
        "I found the Apple iPhone 12 Pro 128GB in Pacific Blue priced at $699.00 and "
        "added it to the cart; the cart page shows the item added."),
    6: (["/search?q=stroller&color=black&min_price=100&max_price=200&min_reviews=20000&min_rating=4",
         "/product/chicco-bravo-trio-travel-system-poetic-black"],
        "Among black strollers between $100 and $200, the Chicco Bravo Trio Travel "
        "System - Poetic Black qualifies: $179.99, rated 4.7 stars with 28,760 reviews "
        "(over 20,000). It offers a 3-in-1 design with an infant car seat."),
    7: (["/search?q=womens+hiking+boots&feature=waterproof&min_rating=4&size=6"],
        "Filtering the women's hiking boots to waterproof, 4+ stars, and size 6 leaves "
        "four boots: Columbia Women's Newton Ridge Plus Hiking Boot ($89.95, 4.5 stars), "
        "Columbia Women's Newton Ridge Hiking Boot ($89.99, 4.6 stars), Merrell Women's "
        "Moab 3 Hiking Boot ($134.95, 4.7 stars), and Timberland Women's Mt. Maddsen "
        "Hiking Boot ($129.00, 4.5 stars). All are waterproof and available in size 6."),
    8: (["/search?q=samsung+galaxy+tablet&sort=price_asc",
         "/product/samsung-galaxy-tab-a7-10-4-32gb"],
        "The cheapest Samsung Android tablet with a 10-10.9 inch screen is the Samsung "
        "Galaxy Tab A7 at $189.99. It has a 10.4\" screen, 32GB storage, and an "
        "8,000mAh battery (4.5 stars, 6,309 reviews)."),
    9: (["/search?q=dog+bed&feature=washable", "/product/bedsure-large-washable-dog-bed-32"],
        "The Bedsure Large Dog Bed qualifies: it is washable (machine washable, washable "
        "cover) and has a length of 32 inches, well over 30 inches. It costs $44.99 with "
        "4.7 stars and 12,415 reviews, and is filled with memory foam."),
    10: (["/search?q=2-year+protection+plan+ps4",
          "/product/2-year-protection-plan-for-ps4-250-300"],
         "The 2-Year Protection Plan for PS4 ($250-$300) by Asurion costs $24.99. It is "
         "rated 4.2 stars with 3,400 reviews. (The 3-year plan costs $34.99.)"),
    11: (["/search?q=kitchen+sink&feature=stainless+steel&sort=price_asc",
          "/product/kindred-ksd30dl-double-bowl-drop-in-sink"],
         "The cheapest stainless steel double-bowl kitchen sink with FREE delivery is "
         "the Kindred KSD30DL Double Bowl Drop-In Sink at $189.99, with a 50/50 double "
         "bowl configuration and free shipping (4.4 stars, 4,586 reviews). The Ruvati, "
         "Elkay and Kraus Standart PRO sinks charge a delivery fee."),
    12: (["/search?q=ride+on+car&min_reviews=100&min_rating=4",
          "/product/best-choice-products-12v-kids-licensed-ride-on-car"],
         "I checked the Best Choice Products 12V Kids Licensed Ride On Car (12,543 "
         "reviews, 4.4 stars). Its top review is 'Best Ride-On We've Owned' (5 stars): "
         "the 4-year-old uses it daily, the 12V battery lasts 45-55 minutes per charge, "
         "the parental remote control is a game-changer, and assembly took two people "
         "about 40 minutes."),
    13: (["/search?q=mens+hoodie&color=black&min_price=25&max_price=50&size=2xl&bestseller=1"],
         "The best-selling black hoodies in men's Big & Tall sizes between $25 and $50 "
         "are: Amazon Essentials Men's Big & Tall Fleece Hoodie - Black at $29.99 "
         "(4.6 stars, 24,549 reviews) and Hanes Men's Big & Tall ComfortBlend EcoSmart "
         "Hoodie - Black at $34.99 (4.7 stars, 24,433 reviews). Both come in LT through "
         "5XL sizes."),
    14: (["/search?q=surge+protector&max_price=25&min_rating=4"],
         "The Belkin Surge Protector with 6ft Cord qualifies: 8 outlets, $19.99, rated "
         "4.7 stars with 3,332 reviews, 1000 joules of surge protection, and it is new."),
    15: (["/search?q=mens+running+shoes&color=black&size=7&min_rating=4&max_price=50",
          "/product/asics-men-s-gel-contend-7-running-shoe-black", "/bag"],
         "I added the ASICS Men's Gel-Contend 7 Running Shoe in Black, size 7 to the "
         "cart. It costs $47.99, is rated 4.6 stars, has 13,311 reviews, and features "
         "GEL cushioning; the cart page confirms the item was added."),
    16: (["/search?q=mens+rhinestone+skull+graphic+shirt",
          "/product/men-s-rhinestone-skull-graphic-t-shirt-black"],
         "For the Men's Rhinestone Skull Graphic T-Shirt (Black, XX-Large), free return "
         "IS available: the item is returnable within 30 days of delivery and ships "
         "back at no cost using the prepaid Amazon return shipping label provided in "
         "Your Orders. The item must be in new, unworn condition with all original tags "
         "attached; refunds post within 3-5 business days after Amazon receives it."),
    17: (["/search?q=baby+products&deal=1&max_price=10"],
         "Baby products currently on sale under $10 include: Huggies Natural Care Baby "
         "Wipes 56ct at $4.99 (was $9.99), Fisher-Price Rattle & Rock Maracas at $6.99 "
         "(was $10.99), and Johnson's Baby Shampoo 20 oz at $7.49 (was $12.99). All are "
         "marked as today's deals."),
    18: (["/", "/deals"],
         "The deal event going on right now is Today's Deals (save up to 50% on select "
         "items). Examples on offer: the Fire TV Stick 4K Max is 33% off ($39.99, was "
         "$59.99), the SanDisk 1TB Ultra microSDXC is 40% off ($89.99, was $149.99), and "
         "the Echo Dot (5th Gen) is 17% off ($49.99, was $59.99)."),
    19: (["/search?q=roman+empire+history&sort=newest"],
         "In the Kindle Store, sorted by newest arrivals, a title that will be released "
         "within a month is 'The Rise of Rome: A New History of the Roman Empire' "
         "(Pre-order, releases 2026-04-23), priced at $14.99 with 4.7 stars. Another "
         "option releasing even sooner is 'Caesar's Legacy: The Roman Empire' "
         "(Pre-order, 2026-04-16) at $12.99."),
    20: (["/search?q=wireless+ergonomic+keyboard&min_rating=4&min_price=40&max_price=60&min_reviews=500"],
         "The Logitech MX Keys Wireless Keyboard qualifies: wireless, ergonomic, "
         "backlit (backlighting with auto-adjust), $54.99, rated 4.8 stars with 18,500 "
         "customer reviews (500+). I saved this product."),
    21: (["/search?q=coffee+maker&min_price=100&max_price=200&min_rating=4"],
         "A qualifying coffee maker is the Ninja CE251 Programmable Coffee Maker: "
         "stainless steel, 12-cup, programmable, $119.99, rated 4.6 stars with 21,128 "
         "reviews (4+ customer rating)."),
    22: (["/search?q=cookware+set&max_price=150"],
         "The T-fal Ultimate Hard Anodized Cookware Set qualifies: non-stick, oven-safe "
         "up to 400F, 12-piece set, $139.99, 4.7 stars with 11,507 reviews - under $150."),
    23: (["/search?q=mens+waterproof+digital+sports+watch&min_price=50&max_price=100"],
         "The Casio G-Shock DW5600 Digital Sports Watch qualifies: waterproof, digital, "
         "with heart rate monitoring, $64.99, rated 4.8 stars with 17,867 reviews - "
         "within the $50 to $100 range."),
    24: (["/search?q=compact+air+fryer&max_price=100&feature=digital"],
         "The Dash Compact Air Fryer qualifies: 2-quart capacity, digital display, auto "
         "shutoff, $44.99, 4.7 stars with 45,979 reviews - under $100."),
    25: (["/search?q=mattress+topper&feature=hypoallergenic+memory+foam&min_price=50&max_price=100"],
         "The LINENSPA Mattress Topper - Queen qualifies: hypoallergenic, memory foam, "
         "queen-sized, $59.99, rated 4.6 stars with 15,016 reviews - within the $50 to "
         "$100 range."),
    26: (["/search?q=portable+bluetooth+speaker&max_price=50&feature=water-resistant"],
         "The Anker Soundcore 2 Portable Bluetooth Speaker qualifies: water-resistant "
         "(IPX7), $39.99, and a 24-hour battery life (at least 10 hours), rated 4.7 "
         "stars with 52,487 reviews."),
    27: (["/search?q=usb+c+hub+macbook+pro&max_price=50&sort=bestseller",
          "/product/anker-5-in-1-usb-c-hub-with-hdmi-and-sd-card"],
         "After sorting by Best Sellers, the one to select is the Anker 5-in-1 USB-C Hub "
         "with HDMI and SD card reader at $25.99 (4.7 stars, 52,000 reviews). It is "
         "MacBook Pro compatible with 5 ports including HDMI and an SD card reader, "
         "under $50."),
    28: (["/search?q=yoga+mat&max_price=50&feature=non-slip+eco-friendly"],
         "The IUGA Eco-Friendly Yoga Mat qualifies: 6mm thick, non-slip, eco-friendly, "
         "$34.99, rated 4.6 stars with 74,822 reviews - under $50."),
    29: (["/search?q=solar+garden+lights&max_price=50"],
         "The BEAU JARDIN Solar Garden Lights qualify: solar-powered LED, 10-pack of "
         "lights, $29.99, rated 4.6 stars with 16,241 reviews - under $50 with a minimum "
         "pack of 10."),
    30: (["/search?q=fiction+book&year=2024&min_reviews=50&sort=rating"],
         "The highest-rated fiction book released in 2024 with at least 50 reviews is "
         "'The Women' at 4.9 stars with 56,000 reviews, released 2024-01-15, priced at "
         "$18.99."),
    31: (["/search?q=compact+digital+camera&min_rating=4&min_price=100&max_price=300"],
         "The Canon PowerShot ELPH 360 HS qualifies: 12x optical zoom (at least 10x), "
         "4.5 stars, $249.99 - within the $100 to $300 range with 10,645 reviews."),
    32: (["/search?q=electric+kettle&min_rating=4"],
         "The COSORI Electric Kettle qualifies: 1.7-liter capacity (at least 1.5L), "
         "stainless steel, 4.7 stars, $39.99, with 25,428 reviews."),
    33: (["/search?q=portable+air+conditioner&feature=300+sq+ft"],
         "For a 300 sq ft room the three suitable portable air conditioners with energy "
         "efficiency ratings are: BLACK+DECKER BPACT08WT (8000 BTU, CEER 7.0) at "
         "$329.99, Midea (10000 BTU, CEER 8.0) at $389.00, and Honeywell MN10CESWW "
         "(10000 BTU, CEER 7.8) at $409.99. Price comparison: the BLACK+DECKER is the "
         "cheapest, the Honeywell is the most expensive, a $80.00 difference between "
         "cheapest and priciest."),
    34: (["/search?q=acrylic+paint+set&max_price=40"],
         "The Castle Art Supplies Acrylic Paint Set qualifies: 24 colors (at least 24), "
         "suitable for canvas painting, $29.99, rated 4.6 stars with 5,098 reviews - "
         "under $40 and beginner-friendly."),
    35: (["/search?q=mens+leather+wallet&max_price=50&feature=rfid"],
         "The Fossil Men's Ingram Leather Bifold Wallet qualifies: RFID blocking, 8 card "
         "slots, $39.99, 4.7 stars. Yes, it is available for FREE delivery (free "
         "shipping)."),
    36: (["/search?q=science+experiment+kit&max_price=30&min_rating=4"],
         "The National Geographic Mega Science Kit qualifies: suitable for ages 8-13 "
         "(Ages 8-14 line), $24.99, rated 4.7 stars with 12,827 reviews - under $30."),
    37: (["/search?q=bedspread&feature=floral", "/product/mellanni-queen-bedspread-floral-print-blue"],
         "The Mellanni Queen Bedspread is a queen-sized floral bedspread, and yes it is "
         "available in blue (Blue, Navy Blue, Teal Blue, Gray, White color options). It "
         "costs $59.99 with 4.7 stars and 6,335 reviews."),
    38: (["/search?q=bird+feeder&feature=anti-squirrel+small-birds"],
         "The Perky-Pet Squirrel-Be-Gone Max Bird Feeder qualifies: suitable for small "
         "birds with an anti-squirrel mechanism, $43.99, 4.6 stars. Yes, it is "
         "available with free shipping."),
    39: (["/search?q=japan+travel+guide&year=2024&min_reviews=20"],
         "The Lonely Planet Japan (Travel Guide) 2024 edition qualifies: published in "
         "2024 with 850 customer reviews (at least 20), $22.99, rated 4.8 stars."),
    40: (["/search?q=womens+yoga+mat&color=purple&max_price=30&min_rating=4",
          "/product/gaiam-essentials-yoga-mat-6mm-purple"],
         "The Gaiam Essentials Yoga Mat in Purple qualifies: 6mm thick (at least 5mm), "
         "4.7 stars, $19.99 (under $30). It is available in 10 colors in total (Purple, "
         "Blue, Pink, Black, Green, Teal, Red, Gray, Yellow, Orange). Return policy: "
         "30-day free returns - return this item for free within 30 days for a full "
         "refund. Delivery policy: FREE delivery Wednesday, Apr 16 (free shipping)."),
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
        "task_id": task_id or f"Amazon--{task}",
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
            __import__("os").environ.get("WH_CONTAINER", "wh-ver-amazon"), "instance_seed")
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
                result = self.execute(task, answer="The requested product is unavailable on Amazon.")
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_foreign_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, task_id="Amazon--999")
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
                    mutate=lambda db: db.execute("UPDATE products SET price = price + 1 WHERE id = 1"))
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "db_state")


    def test_task7_count_answer_with_all_filters_passes(self):
        paths = ["/search?q=womens+hiking+boots&feature=waterproof&min_rating=4&size=6"]
        answer = ("Filtered women's hiking boots to waterproof options in size 6 "
                  "with ratings of 4 stars or higher. There are 4 matching results.")
        result = self.execute(7, paths=paths, answer=answer)
        self.assertTrue(result["pass"], result)

    def test_task7_count_answer_without_filters_fails(self):
        paths = ["/search?q=womens+hiking+boots"]
        answer = ("Filtered women's hiking boots to waterproof options in size 6 "
                  "with ratings of 4 stars or higher. There are 4 matching results.")
        result = self.execute(7, paths=paths, answer=answer)
        self.assertFalse(result["pass"], result)
        self.assertIn(result.get("reason"),
                      ("nav_waterproof_filter_or_product", "answer_lists_all_four"))


    def _make_anon_add_run(self, root, bag_text, answer):
        """Acceptor's failed-run shape: search -> card add -> /bag, no product
        page, no blue filter, no login, no DB row; the identity lives in the
        cart page's recorded DOM text."""
        run = root / "run_anon"
        shots = run / "screenshots"
        shots.mkdir(parents=True)
        paths = ["/", "/search?dept=All&q=Blue+iPhone+12+Pro+128GB", "/bag", "/bag"]
        steps = []
        for i, p in enumerate(paths):
            shot = f"step_{i:03d}.png"
            (shots / shot).write_bytes(PNG)
            steps.append({"step": i, "url": ORIGIN + p, "action": "click",
                          "action_result": {"success": True},
                          "screenshot_after": shot,
                          "observed_text_after": bag_text if i == 2 else "page"})
        trajectory = {
            "task_id": "Amazon--5", "task": "fixture", "start_url": ORIGIN + "/",
            "terminated": True, "termination_reason": "agent_done",
            "final_answer": answer, "steps": steps,
        }
        (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
        return run

    def test_task5_acceptor_anonymous_card_add_passes(self):
        # D1 regression: the acceptor's failed run shape must PASS (identity from
        # the cart page: model name + add confirmation + product 84's $699.00)
        bag_text = ("Added Apple iPhone 12 Pro 128GB to cart. Item added to your "
                    "shopping cart. Shopping Cart $699.00 Subtotal (1 items): $699.00")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            run = self._make_anon_add_run(root, bag_text,
                                          "Added the Blue Apple iPhone 12 Pro 128GB to the cart.")
            result = run_verifier(5, run, initial, initial)
            self.assertTrue(result["pass"], result)

    def test_task5_anonymous_wrong_price_unit_fails(self):
        # a Graphite 128GB unit (wrong color, $679.00) must not pass the anchor
        bag_text = ("Added Apple iPhone 12 Pro 128GB to cart. Item added to your "
                    "shopping cart. Shopping Cart $679.00 Subtotal (1 items): $679.00")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            run = self._make_anon_add_run(root, bag_text,
                                          "Added the Blue Apple iPhone 12 Pro 128GB to the cart.")
            result = run_verifier(5, run, initial, initial)
            self.assertFalse(result["pass"], result)
            self.assertEqual(result.get("reason"), "nav_blue_128gb_identified")

    def test_task5_anonymous_pro_max_bag_fails(self):
        # the Pro Max bag row (name + $849.00) must not pass
        bag_text = ("Added Apple iPhone 12 Pro Max 128GB to cart. Item added to your "
                    "shopping cart. Shopping Cart $849.00 Subtotal (1 items): $849.00")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            run = self._make_anon_add_run(
                root, bag_text,
                "Added the Apple iPhone 12 Pro Max 128GB to the cart.")
            result = run_verifier(5, run, initial, initial)
            self.assertFalse(result["pass"], result)

    def test_task5_pro_max_answer_fails(self):
        # the Pro Max 128GB shares the name prefix; it must not pass task 5
        result = self.execute(5, answer="Added the Apple iPhone 12 Pro Max 128GB in Pacific Blue to the cart.")
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "answer_iphone_12_pro_128gb")


class CartDeltaTests(unittest.TestCase):
    """Task 5 (add to cart): the only allowed DB delta is a cart_items row for
    the qualifying product; any other write must FAIL the verifier."""

    def execute_with_mutation(self, task, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            with sqlite3.connect(after) as connection:
                mutate(connection)
                connection.commit()
            run = make_run(root, task, *POSITIVE[task])
            return run_verifier(task, run, initial, after)

    def test_task5_allows_cart_row_for_qualifying_product(self):
        def add_qualifying(db):
            user_id = db.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()[0]
            db.execute("INSERT INTO cart_items(user_id, product_id, quantity, variant, added_at) "
                       "VALUES (?,?,1,'','2026-09-19 12:00:00')", (user_id, 84))
        result = self.execute_with_mutation(5, add_qualifying)
        self.assertTrue(result["pass"], result)

    def test_task5_rejects_cart_row_for_wrong_product(self):
        def add_wrong(db):
            user_id = db.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()[0]
            db.execute("INSERT INTO cart_items(user_id, product_id, quantity, variant, added_at) "
                       "VALUES (?,?,1,'','2026-09-19 12:00:00')", (user_id, 92))
        result = self.execute_with_mutation(5, add_wrong)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result.get("reason"), "db_state")

    def test_readonly_task_rejects_any_cart_row(self):
        def add_any(db):
            user_id = db.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()[0]
            db.execute("INSERT INTO cart_items(user_id, product_id, quantity, variant, added_at) "
                       "VALUES (?,?,1,'','2026-09-19 12:00:00')", (user_id, 84))
        result = self.execute_with_mutation(8, add_any)
        self.assertFalse(result["pass"], result)


class ContractTests(unittest.TestCase):
    def test_task_file_carries_verifier_and_rubric_for_every_task(self):
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 41)
        self.assertEqual([row["id"] for row in rows], [f"Amazon--{i}" for i in TASKS])
        for row in rows:
            self.assertEqual(
                sorted(row.keys()),
                sorted(["web_name", "id", "ques", "web", "upstream_url",
                        "verifier_path", "judge_rubric"]), row["id"])
            self.assertEqual(row["verifier_path"], f"sites/amazon/verify/verify_{row['id'].split('--')[1]}.py")
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
            self.assertIn(f"'Amazon--{task}'", source)

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
