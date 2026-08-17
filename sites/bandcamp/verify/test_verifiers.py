import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_lib import (
    NAV_ALTERNATIVES,
    PASS_ANSWERS,
    STATEFUL_TASKS,
    TASK_COUNT,
    evaluate,
)


def trajectory(answer, urls):
    return {
        "final_answer": answer,
        "steps": [{"step": number, "url": url}
                  for number, url in enumerate(urls)],
    }


def passing_urls(task_index):
    return [group[0] for group in NAV_ALTERNATIVES[task_index][0]]


def make_state_db(path, completed_task=None):
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, city TEXT, "
        "favorite_format TEXT);"
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, title TEXT, slug TEXT);"
        "CREATE TABLE merch_items (id INTEGER PRIMARY KEY, title TEXT, slug TEXT);"
        "CREATE TABLE format_variants (id INTEGER PRIMARY KEY, name TEXT, "
        "option_a TEXT, option_b TEXT);"
        "CREATE TABLE wishlist_items (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "album_id INTEGER, merch_item_id INTEGER);"
        "CREATE TABLE cart_items (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "album_id INTEGER, merch_item_id INTEGER, format_variant_id INTEGER, "
        "quantity INTEGER);"
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "order_number TEXT, status TEXT, shipping_line1 TEXT, "
        "shipping_city TEXT, shipping_country TEXT);"
        "CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, "
        "title TEXT, variant_label TEXT, quantity INTEGER);"
        "INSERT INTO users VALUES (1, 'alice.j@test.com', 'Seattle', 'vinyl');"
        "INSERT INTO users VALUES (2, 'bob.c@test.com', 'Chicago', 'digital');"
        "INSERT INTO users VALUES (3, 'david.k@test.com', 'Portland', 'shirt');"
        "INSERT INTO albums VALUES (1, 'Machine Prayer', 'machine-prayer');"
        "INSERT INTO albums VALUES (2, 'Signal Debt', 'signal-debt');"
        "INSERT INTO merch_items VALUES "
        "(1, 'Soft Locale Drift Hoodie', 'soft-locale-drift-hoodie');"
        "INSERT INTO merch_items VALUES "
        "(2, 'Cinder Plaza Blueprint Fever Poster', "
        "'cinder-plaza-blueprint-fever-poster');"
        "INSERT INTO format_variants VALUES (1, 'Drift Hoodie', 'M', 'Stone');"
        "INSERT INTO format_variants VALUES (2, 'Digital Album', '', '');"
        "INSERT INTO format_variants VALUES (3, 'Signed', '18x24', '');"
        "INSERT INTO cart_items VALUES (1, 2, 2, NULL, 2, 1);"
        "INSERT INTO cart_items VALUES (2, 2, NULL, 2, 3, 1);"
        "INSERT INTO orders VALUES (1, 2, 'BC-20260409-0003', 'delivered', "
        "'77 Fulton Market', 'Chicago', 'United States');"
    )
    if completed_task == 3:
        connection.execute(
            "INSERT INTO wishlist_items VALUES (1, 1, 1, NULL)"
        )
    elif completed_task == 4:
        connection.execute(
            "INSERT INTO cart_items VALUES (3, 2, NULL, 1, 1, 1)"
        )
    elif completed_task == 7:
        connection.executescript(
            "DELETE FROM cart_items WHERE user_id=2;"
            "INSERT INTO orders VALUES (2, 2, 'BC-20260501-0006', 'paid', "
            "'77 Fulton Market', 'Chicago', 'United States');"
            "INSERT INTO order_items VALUES "
            "(1, 2, 'Signal Debt', 'Digital Album', 1);"
            "INSERT INTO order_items VALUES "
            "(2, 2, 'Cinder Plaza Blueprint Fever Poster', 'Signed / 18x24', 1);"
        )
    elif completed_task == 8:
        connection.execute(
            "UPDATE users SET city='Eugene', favorite_format='vinyl' WHERE id=3"
        )
    connection.commit()
    connection.close()


class BandcampVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.initial_db = str(Path(cls.tmp.name) / "initial.db")
        make_state_db(cls.initial_db)
        cls.after_dbs = {}
        for task_index in STATEFUL_TASKS:
            path = str(Path(cls.tmp.name) / f"after-{task_index}.db")
            make_state_db(path, completed_task=task_index)
            cls.after_dbs[task_index] = path

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, index, answer, urls, completed=True):
        after = self.after_dbs.get(index, self.initial_db)
        if not completed:
            after = self.initial_db
        return evaluate(
            index,
            trajectory(answer, urls),
            initial_db=self.initial_db,
            after_db=after,
        )

    def test_all_eighteen_pass_cases(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index, PASS_ANSWERS[index], passing_urls(index)
                )
                self.assertTrue(result["pass"], result)

    def test_all_eighteen_no_op_runs_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, "", ["http://localhost:40016/"])
                self.assertFalse(result["pass"], result)

    def test_all_eighteen_prior_knowledge_shortcuts_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    PASS_ANSWERS[index],
                    ["http://localhost:40016/"],
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], "required_navigation")

    def test_all_eighteen_wrong_answers_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    "This is definitely the wrong answer.",
                    passing_urls(index),
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], "frozen_answer")

    def test_each_stateful_claim_without_database_change_fails(self):
        expected_reason = {
            3: "wishlist_after_state",
            4: "cart_after_state",
            7: "checkout_after_state",
            8: "profile_after_state",
        }
        for index in sorted(STATEFUL_TASKS):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    PASS_ANSWERS[index],
                    passing_urls(index),
                    completed=False,
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], expected_reason[index])

    def test_task_file_has_eighteen_grading_contracts(self):
        task_path = Path(__file__).parents[1] / "tasks.jsonl"
        rows = [json.loads(line) for line in task_path.read_text().splitlines()]
        self.assertEqual(len(rows), TASK_COUNT)
        for index, row in enumerate(rows):
            self.assertEqual(
                row.get("verifier_path"),
                f"sites/bandcamp/verify/verify_{index}.py",
            )
            self.assertTrue(row.get("judge_rubric", "").endswith("visited."))
            self.assertNotIn("answer", row)
            self.assertEqual(row["web"], "http://localhost:40016/")
            self.assertTrue(
                (Path(__file__).parent / f"verify_{index}.py").exists()
            )

    def test_all_wrapper_exit_codes(self):
        verify_dir = Path(__file__).parent
        for index in range(TASK_COUNT):
            run_dir = Path(self.tmp.name) / f"run-{index}"
            run_dir.mkdir()
            run_path = run_dir / "trajectory.json"
            command = [
                sys.executable,
                str(verify_dir / f"verify_{index}.py"),
                "--run_dir",
                str(run_dir),
                "--initial_db",
                self.initial_db,
                "--after_db",
                self.after_dbs.get(index, self.initial_db),
            ]

            run_path.write_text(json.dumps(trajectory(
                PASS_ANSWERS[index], passing_urls(index)
            )))
            passed = subprocess.run(command, capture_output=True, text=True)
            with self.subTest(index=index, case="pass"):
                self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

            run_path.write_text(json.dumps(trajectory(
                "", ["http://localhost:40016/"]
            )))
            failed = subprocess.run(command, capture_output=True, text=True)
            with self.subTest(index=index, case="no_op"):
                self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()
