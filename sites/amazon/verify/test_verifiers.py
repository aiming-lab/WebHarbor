"""Positive, negative, and legal-alternative tests for every Amazon verifier."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parent
SEED_DB = VERIFY_DIR.parent / "instance_seed" / "amazon_store.db"
BASE = "http://localhost:40001"
TASKS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 21, 22, 27, 30, 39, 40)


def url(path: str) -> str:
    return BASE + path


def navigate(path: str) -> dict:
    return {"url": url(path), "action": "navigate", "params": {}}


def click(path: str, destination: str) -> dict:
    return {"url": url(path), "url_after": url(destination), "action": "click", "params": {}}


def enter(path: str, value: str) -> dict:
    return {"url": url(path), "action": "input", "params": {"text": value}}


def open_result(search_path: str, slug: str) -> list[dict]:
    product = f"/product/{slug}"
    return [navigate(search_path), click(search_path, product), navigate(product)]


def login_steps() -> list[dict]:
    return [
        navigate("/login"),
        enter("/login", "demo@amazon.com"),
        enter("/login", "demo1234"),
        click("/login", "/"),
        navigate("/"),
    ]


def next_id(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COALESCE(MAX(id), 0) + 1 FROM "{table}"').fetchone()[0])


class VerifierTests(unittest.TestCase):
    maxDiff = None

    def run_verifier(
        self,
        task: int,
        steps: Any,
        answer: str,
        mutate=None,
        baseline_mutate=None,
        task_id: str | None = None,
        malformed: bool = False,
    ) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory(prefix=f"amazon-verify-{task}-") as directory:
            root = Path(directory)
            initial = root / "initial.db"
            after = root / "after.db"
            run_dir = root / "run"
            run_dir.mkdir()
            shutil.copy2(SEED_DB, initial)
            shutil.copy2(SEED_DB, after)
            if baseline_mutate:
                for snapshot in (initial, after):
                    connection = sqlite3.connect(snapshot)
                    try:
                        baseline_mutate(connection)
                        connection.commit()
                    finally:
                        connection.close()
            if mutate:
                connection = sqlite3.connect(after)
                try:
                    mutate(connection)
                    connection.commit()
                finally:
                    connection.close()
            final_url = url("/")
            if isinstance(steps, list) and steps and isinstance(steps[-1], dict):
                final_url = steps[-1].get("url_after", steps[-1].get("url", final_url))
            trajectory = {
                "task_id": task_id or f"Amazon--{task}",
                "start_url": url("/"),
                "steps": steps,
                "final_url": final_url,
                "final_answer": answer,
            }
            trajectory_path = run_dir / "trajectory.json"
            trajectory_path.write_text("{bad json" if malformed else json.dumps(trajectory), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_DIR / f"verify_{task}.py"),
                    "--run_dir", str(run_dir),
                    "--initial_db", str(initial),
                    "--after_db", str(after),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            try:
                verdict = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                self.fail(f"task {task} emitted invalid JSON: stdout={result.stdout!r} stderr={result.stderr!r}: {error}")
            return result.returncode, verdict

    @staticmethod
    def mutate_wishlist(connection: sqlite3.Connection, slug: str = "women-s-izod-swingflex-golf-polo") -> None:
        user_id = connection.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()[0]
        product_id = connection.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()[0]
        connection.execute(
            "INSERT INTO wishlist_items(id,user_id,product_id,added_at) VALUES(?,?,?,?)",
            (next_id(connection, "wishlist_items"), user_id, product_id, "2026-09-13 10:00:00"),
        )

    @staticmethod
    def mutate_cart(connection: sqlite3.Connection, slug: str = "apple-iphone-12-pro-128gb") -> None:
        user_id = connection.execute("SELECT id FROM users WHERE email='demo@amazon.com'").fetchone()[0]
        product_id = connection.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()[0]
        connection.execute(
            "INSERT INTO cart_items(id,user_id,product_id,quantity,variant,added_at) VALUES(?,?,?,?,?,?)",
            (next_id(connection, "cart_items"), user_id, product_id, 1, "Color: Pacific Blue, Storage: 128GB", "2026-09-13 10:00:00"),
        )

    @staticmethod
    def set_product_spec(connection: sqlite3.Connection, slug: str, key: str, value: str) -> None:
        row = connection.execute("SELECT specs FROM products WHERE slug=?", (slug,)).fetchone()
        specs = json.loads(row[0])
        specs[key] = value
        connection.execute("UPDATE products SET specs=? WHERE slug=?", (json.dumps(specs), slug))

    def positive_case(self, task: int):
        cases = {
            0: (open_result("/search?q=Xbox+controller&color=green&min_rating=4", "xbox-wireless-controller-velocity-green"), "Xbox Wireless Controller — Velocity Green, rated 4.7 stars.", None),
            1: (login_steps() + open_result("/search?q=golf+polo&size=M&min_price=50&max_price=75&sort=price_asc", "women-s-izod-swingflex-golf-polo") + [click("/product/women-s-izod-swingflex-golf-polo", "/product/women-s-izod-swingflex-golf-polo"), navigate("/wishlist")], "Saved Women's IZOD SwingFlex Golf Polo at $52.00.", self.mutate_wishlist),
            2: (open_result("/search?q=gaming+desktop", "hp-omen-25l-gaming-desktop"), "HP OMEN 25L Gaming Desktop — Windows 11 Home, 1TB SSD.", None),
            3: ([navigate("/search?q=climbing&sort=price_desc")], "1. Mammut 9.5 Crag Classic Climbing Rope 60m — $219.95\n2. Evolv Shaman Climbing Shoes — $179.00\n3. Petzl GriGri Plus Belay Device — $149.95", None),
            4: ([navigate("/search?q=Nintendo+Switch+Lite&condition=Used+-+Good&sort=price_asc")], "Nintendo Switch Lite - Gray, Used - Good, $149.99.", None),
            5: (login_steps() + open_result("/search?q=iPhone+12+Pro+128GB&color=blue", "apple-iphone-12-pro-128gb") + [click("/product/apple-iphone-12-pro-128gb", "/bag"), navigate("/bag")], "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $699.00.", self.mutate_cart),
            6: (open_result("/search?q=stroller&color=black&min_price=100&max_price=200&min_rating=4", "chicco-bravo-trio-travel-system-poetic-black"), "Chicco Bravo Trio Travel System - Poetic Black — 4.7 stars, 28,760 reviews.", None),
            7: (open_result("/search?q=hiking+boots&feature=waterproof&min_rating=4&size=6", "merrell-women-s-moab-3-waterproof-hiking-boot"), "Merrell Women's Moab 3 Hiking Boot is waterproof, rated 4.7, and size 6 is available.", None),
            8: (open_result("/search?q=Samsung+tablet&brand=Samsung&sort=price_asc", "samsung-galaxy-tab-a7-10-4-32gb"), "Samsung Galaxy Tab A7 — 10.4-inch screen, $189.99.", None),
            9: (open_result("/search?q=dog+bed&feature=washable", "amazon-basics-pet-dog-bed-large-34-washable"), "Amazon Basics Pet Dog Bed Large — 34 inches long and machine washable.", None),
            10: (open_result("/search?q=PlayStation+4", "2-year-protection-plan-for-ps4-250-300"), "2-Year Protection Plan for PS4 ($250-$300) costs $24.99.", None),
            12: (open_result("/search?q=Ride+On+Car", "best-choice-products-12v-kids-licensed-ride-on-car"), "Best Choice Products 12V Kids Licensed Ride On Car — top review 'Best Ride-On We've Owned' by Demo Customer.", None),
            13: ([navigate("/search?q=hoodie&color=black&min_price=25&max_price=50&bestseller=1")], "Hanes Men's Big & Tall ComfortBlend EcoSmart Hoodie - Black — $34.99\nAmazon Essentials Men's Big & Tall Fleece Hoodie - Black — $29.99", None),
            14: (open_result("/search?q=surge+protector&condition=New&max_price=25&min_rating=4", "belkin-8-outlet-surge-protector-with-6ft-cord"), "Belkin Surge Protector with 6ft Cord — 8 outlets, 4.7 stars, $19.99.", None),
            21: (open_result("/search?q=coffee+maker&min_price=100&max_price=200&min_rating=4", "hamilton-beach-12-cup-programmable-coffee-maker-stainless-steel"), "Hamilton Beach Programmable Coffee Maker — 12 cups, 4.5 stars, $109.99.", None),
            22: (open_result("/search?q=cookware&max_price=150", "t-fal-ultimate-hard-anodized-nonstick-12-piece-cookware-set"), "T-fal Ultimate Hard Anodized Cookware Set — 12 pieces, nonstick and oven-safe, $139.99.", None),
            27: (open_result("/search?q=USB-C+hub&max_price=50&sort=bestseller", "anker-5-in-1-usb-c-hub-with-hdmi-and-sd-card"), "Anker 5-in-1 USB-C Hub — 5 ports, $25.99.", None),
            30: ([navigate("/search?q=fiction+book+2024&sort=rating")], "The Women — 4.9 stars from 56,000 reviews.", None),
            39: (open_result("/search?q=Japan+travel+guide+2024", "lonely-planet-japan-travel-guide-2024-edition"), "Lonely Planet Japan (Travel Guide) — published 2024, 850 reviews, $22.99.", None),
            40: (open_result("/search?q=yoga+mat&color=purple&max_price=30&min_rating=4", "gaiam-essentials-yoga-mat-6mm-purple"), "Gaiam Essentials Yoga Mat has 10 colors. Return policy: 30-day free returns. Return this item for free within 30 days for a full refund. Delivery: FREE delivery Wednesday, Apr 16.", None),
        }
        return cases[task]

    def test_all_positive_cases(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_wrong_task_replay_fails_every_verifier(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate, task_id="Amazon--999")
                self.assertNotEqual(0, code)
                self.assertEqual("task_id_matches", verdict["reason"])

    def test_answer_only_fails_every_verifier(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, [], answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_foreign_origin_fails_every_verifier(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                steps = [{"url": "https://attacker.invalid/search?q=amazon", "action": "navigate", "params": {}}]
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_wrong_answers_fail_every_verifier(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                steps, _, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, "The answer is not the requested result.", mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_read_only_tasks_reject_database_changes(self) -> None:
        read_only = [task for task in TASKS if task not in (1, 5)]

        def mutate(connection: sqlite3.Connection) -> None:
            connection.execute("UPDATE users SET city='Unrelated mutation' WHERE email='demo@amazon.com'")

        for task in read_only:
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_state_tasks_require_exact_state_change(self) -> None:
        for task in (1, 5):
            with self.subTest(task=task, case="no-op"):
                steps, answer, _ = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

        steps, answer, _ = self.positive_case(1)
        code, verdict = self.run_verifier(1, steps, answer, lambda connection: self.mutate_wishlist(connection, "women-s-classic-pique-golf-polo"))
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

        steps, answer, _ = self.positive_case(5)
        code, verdict = self.run_verifier(5, steps, answer, lambda connection: self.mutate_cart(connection, "apple-iphone-12-pro-max-128gb-pacific-blue"))
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_state_tasks_reject_unrelated_mutations(self) -> None:
        for task, base_mutate in ((1, self.mutate_wishlist), (5, self.mutate_cart)):
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)

                def mutate(connection: sqlite3.Connection, base_mutate=base_mutate) -> None:
                    base_mutate(connection)
                    connection.execute("UPDATE users SET city='Unrelated mutation' WHERE email='demo@amazon.com'")

                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_state_tasks_preserve_other_accounts_rows(self) -> None:
        def seed_other_wishlist(connection: sqlite3.Connection) -> None:
            user_id = connection.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]
            product_id = connection.execute("SELECT id FROM products ORDER BY id LIMIT 1").fetchone()[0]
            connection.execute(
                "INSERT INTO wishlist_items(id,user_id,product_id,added_at) VALUES(?,?,?,?)",
                (next_id(connection, "wishlist_items"), user_id, product_id, "2026-09-13 09:00:00"),
            )

        steps, answer, _ = self.positive_case(1)

        def mutate_wishlist_and_delete_other(connection: sqlite3.Connection) -> None:
            self.mutate_wishlist(connection)
            connection.execute(
                "DELETE FROM wishlist_items WHERE user_id=(SELECT id FROM users WHERE email='alice.j@test.com')"
            )

        code, verdict = self.run_verifier(
            1,
            steps,
            answer,
            mutate_wishlist_and_delete_other,
            baseline_mutate=seed_other_wishlist,
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

        steps, answer, _ = self.positive_case(5)

        def mutate_cart_and_delete_other(connection: sqlite3.Connection) -> None:
            self.mutate_cart(connection)
            connection.execute(
                "DELETE FROM cart_items WHERE user_id<>(SELECT id FROM users WHERE email='demo@amazon.com')"
            )

        code, verdict = self.run_verifier(5, steps, answer, mutate_cart_and_delete_other)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_numeric_filter_spellings_pass(self) -> None:
        cases = {
            0: open_result(
                "/search?q=Xbox+controller&color=green&min_rating=4.00",
                "xbox-wireless-controller-velocity-green",
            ),
            1: login_steps()
            + open_result(
                "/search?q=golf+polo&size=M&min_price=50.00&max_price=75.00&sort=price_asc",
                "women-s-izod-swingflex-golf-polo",
            )
            + [
                click(
                    "/product/women-s-izod-swingflex-golf-polo",
                    "/product/women-s-izod-swingflex-golf-polo",
                ),
                navigate("/wishlist"),
            ],
            14: open_result(
                "/search?q=surge+protector&condition=New&max_price=25.00&min_rating=4.00",
                "belkin-8-outlet-surge-protector-with-6ft-cord",
            ),
        }
        for task, steps in cases.items():
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_task_wording_and_compact_storage_searches_pass(self) -> None:
        cases = {
            5: login_steps()
            + open_result(
                "/search?q=iPhone+12+Pro+128+GB&color=blue",
                "apple-iphone-12-pro-128gb",
            )
            + [click("/product/apple-iphone-12-pro-128gb", "/bag"), navigate("/bag")],
            8: open_result(
                "/search?q=Samsung+tablets&brand=Samsung&sort=price_asc",
                "samsung-galaxy-tab-a7-10-4-32gb",
            ),
            9: open_result(
                "/search?q=dog+beds&feature=washable",
                "amazon-basics-pet-dog-bed-large-34-washable",
            ),
            30: [navigate("/search?q=fiction+books+released+in+2024&sort=rating")],
        }
        for task, steps in cases.items():
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_mirror_sort_aliases_pass(self) -> None:
        cases = {
            1: login_steps()
            + open_result(
                "/search?q=golf+polos&size=M&min_price=50&max_price=75&sort=low_to_high",
                "women-s-izod-swingflex-golf-polo",
            )
            + [
                click(
                    "/product/women-s-izod-swingflex-golf-polo",
                    "/product/women-s-izod-swingflex-golf-polo",
                ),
                navigate("/wishlist"),
            ],
            3: [navigate("/search?q=climbing&sort=high_to_low")],
            27: open_result(
                "/search?q=USB-C+hubs&max_price=50&sort=popular",
                "anker-5-in-1-usb-c-hub-with-hdmi-and-sd-card",
            ),
            30: [navigate("/search?q=fiction+books+2024&sort=customer_review")],
        }
        for task, steps in cases.items():
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_equivalent_storage_answer_spelling_passes(self) -> None:
        steps, _, _ = self.positive_case(2)
        answer = "HP OMEN 25L Gaming Desktop — Windows 11 Home, 1 TB SSD."
        code, verdict = self.run_verifier(2, steps, answer)
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

    def test_negated_oven_safe_answer_is_rejected(self) -> None:
        steps, _, _ = self.positive_case(22)
        answer = "T-fal Ultimate Hard Anodized Cookware Set — 12 pieces, nonstick. Oven safe: No. $139.99."
        code, verdict = self.run_verifier(22, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_about_blank_before_target_navigation_passes(self) -> None:
        steps, answer, _ = self.positive_case(0)
        steps = [{"url": "about:blank", "action": "navigate", "params": {}}] + steps
        code, verdict = self.run_verifier(0, steps, answer)
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

    def test_malformed_steps_type_emits_structured_fail(self) -> None:
        code, verdict = self.run_verifier(0, "not-a-step-array", "answer")
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])
        self.assertEqual("verifier_exception", verdict["reason"])

    def test_search_filters_remain_fail_closed(self) -> None:
        cases = (
            "/search?q=strollers&color=black&min_price=100&max_price=200&min_rating=3",
            "/search?q=strollers&color=black&min_price=100&max_price=200&min_rating=four",
            "/search?q=strollers&min_price=100&max_price=200&min_rating=4",
        )
        _, answer, _ = self.positive_case(6)
        for search_path in cases:
            with self.subTest(search_path=search_path):
                steps = open_result(search_path, "chicco-bravo-trio-travel-system-poetic-black")
                code, verdict = self.run_verifier(6, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_noneligible_or_unclicked_result_is_rejected(self) -> None:
        search_path = "/search?q=Samsung+tablets&brand=Samsung&sort=price_asc"
        cases = (
            open_result(search_path, "samsung-galaxy-tab-s7-11-128gb"),
            [navigate(search_path), navigate("/product/samsung-galaxy-tab-a7-10-4-32gb")],
        )
        _, answer, _ = self.positive_case(8)
        for steps in cases:
            with self.subTest(steps=steps):
                code, verdict = self.run_verifier(8, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_cart_increment_path_passes_and_exact_delta_is_enforced(self) -> None:
        steps, _, _ = self.positive_case(5)

        def increment_target(connection: sqlite3.Connection, amount: int = 1) -> None:
            connection.execute(
                "UPDATE cart_items SET quantity=quantity+? WHERE product_id=(SELECT id FROM products WHERE slug=?)",
                (amount, "apple-iphone-12-pro-128gb"),
            )

        code, verdict = self.run_verifier(
            5,
            steps,
            "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $1398.00.",
            increment_target,
            baseline_mutate=self.mutate_cart,
        )
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

        code, verdict = self.run_verifier(
            5,
            steps,
            "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $2097.00.",
            lambda connection: increment_target(connection, 2),
            baseline_mutate=self.mutate_cart,
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

        def add_two(connection: sqlite3.Connection) -> None:
            self.mutate_cart(connection)
            connection.execute(
                "UPDATE cart_items SET quantity=2 WHERE product_id=(SELECT id FROM products WHERE slug=?)",
                ("apple-iphone-12-pro-128gb",),
            )

        code, verdict = self.run_verifier(
            5,
            steps,
            "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $1398.00.",
            add_two,
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_state_tasks_preserve_preexisting_demo_rows(self) -> None:
        def seed_prior_wishlist(connection: sqlite3.Connection) -> None:
            self.mutate_wishlist(connection, "women-s-classic-pique-golf-polo")

        steps, answer, _ = self.positive_case(1)
        code, verdict = self.run_verifier(
            1,
            steps,
            answer,
            self.mutate_wishlist,
            baseline_mutate=seed_prior_wishlist,
        )
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

        def seed_prior_cart(connection: sqlite3.Connection) -> None:
            user_id = connection.execute(
                "SELECT id FROM users WHERE email='demo@amazon.com'"
            ).fetchone()[0]
            product_id = connection.execute(
                "SELECT id FROM products WHERE slug='echo-dot-5th-gen-smart-speaker-with-alexa'"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO cart_items(id,user_id,product_id,quantity,variant,added_at) VALUES(?,?,?,?,?,?)",
                (next_id(connection, "cart_items"), user_id, product_id, 2, "", "2026-09-13 09:00:00"),
            )

        steps, _, _ = self.positive_case(5)
        code, verdict = self.run_verifier(
            5,
            steps,
            "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $798.98.",
            self.mutate_cart,
            baseline_mutate=seed_prior_cart,
        )
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

        def add_target_and_delete_prior(connection: sqlite3.Connection) -> None:
            self.mutate_cart(connection)
            connection.execute(
                "DELETE FROM cart_items WHERE product_id=(SELECT id FROM products WHERE slug='echo-dot-5th-gen-smart-speaker-with-alexa')"
            )

        code, verdict = self.run_verifier(
            5,
            steps,
            "Added Apple iPhone 12 Pro 128GB. Cart subtotal: $699.00.",
            add_target_and_delete_prior,
            baseline_mutate=seed_prior_cart,
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_state_change_on_another_account_is_rejected(self) -> None:
        def add_to_alice_cart(connection: sqlite3.Connection) -> None:
            user_id = connection.execute(
                "SELECT id FROM users WHERE email='alice.j@test.com'"
            ).fetchone()[0]
            product_id = connection.execute(
                "SELECT id FROM products WHERE slug='apple-iphone-12-pro-128gb'"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO cart_items(id,user_id,product_id,quantity,variant,added_at) VALUES(?,?,?,?,?,?)",
                (next_id(connection, "cart_items"), user_id, product_id, 1, "", "2026-09-13 10:00:00"),
            )

        steps, answer, _ = self.positive_case(5)
        code, verdict = self.run_verifier(5, steps, answer, add_to_alice_cart)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_lower_ranked_products_are_rejected(self) -> None:
        cases = {
            8: (
                open_result(
                    "/search?q=Samsung+tablets&brand=Samsung&sort=price_asc",
                    "samsung-galaxy-tab-s6-lite-10-4-64gb",
                ),
                "Samsung Galaxy Tab S6 Lite — 10.4-inch screen, $349.99.",
            ),
            27: (
                open_result(
                    "/search?q=USB-C+hubs&max_price=50&sort=bestseller",
                    "anker-7-in-1-usb-c-hub-for-macbook-pro",
                ),
                "Anker 7-in-1 USB-C Hub for MacBook Pro — 7 ports, $34.99.",
            ),
            30: (
                [navigate("/search?q=fiction+books+2024&sort=rating")],
                "Fourth Wing (The Empyrean) — 4.8 stars from 285,000 reviews.",
            ),
        }
        for task, (steps, answer) in cases.items():
            with self.subTest(task=task):
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_general_purple_yoga_mat_is_a_legal_alternative(self) -> None:
        steps = open_result(
            "/search?q=yoga+mats&color=purple&max_price=30&min_rating=4",
            "gaiam-essentials-thick-yoga-mat-2-5-inch-10mm",
        )
        answer = (
            "Gaiam Essentials Yoga Mat has 5 colors. "
            "Return policy: 30-day return policy. Eligible for free returns. "
            "Delivery: FREE delivery in 2 days."
        )
        code, verdict = self.run_verifier(40, steps, answer)
        self.assertEqual(0, code, verdict)
        self.assertTrue(verdict["pass"], verdict)

    def test_non_waterproof_boot_is_rejected(self) -> None:
        slug = "ahnu-women-s-montara-iii-hiking-boot-non-waterproof"
        steps = open_result(
            "/search?q=hiking+boots&feature=waterproof&min_rating=4&size=6",
            slug,
        )
        answer = "Ahnu Women's Montara III Leather Hiking Boot is waterproof, rated 4.3, and size 6 is available."
        code, verdict = self.run_verifier(7, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_explicit_negative_specs_are_rejected(self) -> None:
        cases = {
            22: (
                "t-fal-ultimate-hard-anodized-nonstick-12-piece-cookware-set",
                "Oven Safe",
            ),
            27: ("anker-5-in-1-usb-c-hub-with-hdmi-and-sd-card", "HDMI"),
        }
        for task, (slug, key) in cases.items():
            with self.subTest(task=task):
                steps, answer, _ = self.positive_case(task)

                def set_negative(connection: sqlite3.Connection, slug=slug, key=key) -> None:
                    self.set_product_spec(connection, slug, key, "No")

                code, verdict = self.run_verifier(
                    task,
                    steps,
                    answer,
                    baseline_mutate=set_negative,
                )
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])

    def test_legal_alternative_products_pass(self) -> None:
        alternatives = {
            6: (open_result("/search?q=stroller&color=black&min_price=100&max_price=200&min_rating=4", "joovy-scooter-x2-double-stroller-black"), "Joovy Scooter X2 Double Stroller - Black — 4.7 stars and 25,400 reviews."),
            7: (open_result("/search?q=hiking+boots&feature=waterproof&min_rating=4&size=6", "columbia-women-s-newton-ridge-waterproof-boot"), "Columbia Women's Newton Ridge Hiking Boot is waterproof, rated 4.6, and available in size 6."),
            9: (open_result("/search?q=dog+bed&feature=washable", "bedsure-large-washable-dog-bed-32"), "Bedsure Large Dog Bed is washable and 32 inches long."),
            14: (open_result("/search?q=surge+protector&condition=New&max_price=25&min_rating=4", "philips-6-outlet-surge-protector-power-strip"), "Philips Surge Protector Power Strip — 6 outlets, 4.6 stars, $12.99."),
            22: (open_result("/search?q=cookware&max_price=150", "greenlife-soft-grip-16-piece-ceramic-nonstick-cookware-set"), "GreenLife Soft Grip Ceramic Cookware Set — 16 pieces, non-stick and oven-safe, $114.99."),
            39: (open_result("/search?q=Japan+travel+guide+2024", "national-geographic-traveler-japan-2024"), "National Geographic Traveler Japan — 2024, 95 reviews, $27.99."),
            40: (open_result("/search?q=yoga+mat&color=purple&max_price=30&min_rating=4", "tumaz-yoga-mat-8mm-plum-purple"), "Tumaz Yoga Mat has 11 colors. Return policy: 30-day free returns. Return this item for free within 30 days for a full refund. Delivery: FREE delivery Wednesday, Apr 16."),
        }
        for task, (steps, answer) in alternatives.items():
            with self.subTest(task=task):
                code, verdict = self.run_verifier(task, steps, answer)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_ranked_answers_reject_swapped_values(self) -> None:
        steps, _, _ = self.positive_case(3)
        answer = "1. Evolv Shaman Climbing Shoes — $219.95\n2. Mammut 9.5 Crag Classic Climbing Rope 60m — $179.00\n3. Petzl GriGri Plus Belay Device — $149.95"
        code, verdict = self.run_verifier(3, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

        steps, _, _ = self.positive_case(13)
        answer = "Hanes Men's Big & Tall ComfortBlend EcoSmart Hoodie - Black — $29.99\nAmazon Essentials Men's Big & Tall Fleece Hoodie - Black — $34.99"
        code, verdict = self.run_verifier(13, steps, answer)
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_list_tasks_reject_extra_products(self) -> None:
        steps, answer, _ = self.positive_case(3)
        code, verdict = self.run_verifier(
            3,
            steps,
            answer + "\n4. Trango Squid Quickdraws — $89.95",
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

        steps, answer, _ = self.positive_case(13)
        code, verdict = self.run_verifier(
            13,
            steps,
            answer + "\nChampion Men's Big & Tall Reverse Weave Hoodie - Black — $54.00",
        )
        self.assertNotEqual(0, code)
        self.assertFalse(verdict["pass"])

    def test_malformed_trajectory_emits_structured_fail(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                code, verdict = self.run_verifier(task, [], "", malformed=True)
                self.assertNotEqual(0, code)
                self.assertFalse(verdict["pass"])
                self.assertEqual("verifier_exception", verdict["reason"])

    def test_malformed_invocation_emits_structured_fail(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VERIFY_DIR / "verify_0.py")],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        verdict = json.loads(result.stdout)
        self.assertFalse(verdict["pass"])
        self.assertEqual("verifier_exception", verdict["reason"])


if __name__ == "__main__":
    unittest.main()
