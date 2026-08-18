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
        "CREATE TABLE user (id INTEGER PRIMARY KEY, email TEXT);"
        "CREATE TABLE recipe (id INTEGER PRIMARY KEY, title TEXT, slug TEXT);"
        "CREATE TABLE shopping_list (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "name TEXT, items_json TEXT);"
        "CREATE TABLE meal_plan_item (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "recipe_id INTEGER, day TEXT, meal_type TEXT);"
        "INSERT INTO user VALUES (1, 'bob.c@test.com');"
        "INSERT INTO recipe VALUES "
        "(1, 'Shrimp Scampi with Pasta', 'shrimp-scampi');"
        "INSERT INTO recipe VALUES (2, 'Waffles', 'waffles');"
        "INSERT INTO shopping_list VALUES "
        "(1, 1, 'Weeknight Dinners', '[]');"
        "INSERT INTO meal_plan_item VALUES "
        "(1, 1, 1, 'sunday', 'dinner');"
    )
    if completed_task == 12:
        connection.execute(
            "INSERT INTO shopping_list VALUES (2, 1, 'Cookpad Staples', NULL)"
        )
    elif completed_task == 13:
        connection.executescript(
            "DELETE FROM meal_plan_item WHERE user_id=1 "
            "AND day='sunday' AND meal_type='dinner';"
            "INSERT INTO meal_plan_item VALUES "
            "(2, 1, 2, 'sunday', 'dinner');"
        )
    connection.commit()
    connection.close()


class CookpadVerifierTests(unittest.TestCase):
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

    def test_all_nineteen_pass_cases(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index, PASS_ANSWERS[index], passing_urls(index)
                )
                self.assertTrue(result["pass"], result)

    def test_all_nineteen_no_op_runs_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, "", ["http://localhost:40016/"])
                self.assertFalse(result["pass"], result)

    def test_all_nineteen_prior_knowledge_shortcuts_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    PASS_ANSWERS[index],
                    ["http://localhost:40016/"],
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], "required_navigation")

    def test_all_nineteen_wrong_answers_fail(self):
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
            12: "shopping_list_after_state",
            13: "meal_plan_after_state",
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

    def test_task_file_has_nineteen_grading_contracts(self):
        task_path = Path(__file__).parents[1] / "tasks.jsonl"
        rows = [json.loads(line) for line in task_path.read_text().splitlines()]
        self.assertEqual(len(rows), TASK_COUNT)
        auth_tasks = {7, 8, 9, 12, 13, 14, 15}
        for index, row in enumerate(rows):
            self.assertEqual(
                row.get("verifier_path"),
                f"sites/cookpad/verify/verify_{index}.py",
            )
            self.assertTrue(row.get("judge_rubric", "").endswith("visited."))
            self.assertNotIn("answer", row)
            self.assertEqual(row["web"], "http://localhost:40016/")
            self.assertTrue(
                (Path(__file__).parent / f"verify_{index}.py").exists()
            )
            if index in auth_tasks:
                self.assertIn("TestPass123!", row["ques"])

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
                self.assertEqual(
                    passed.returncode, 0, passed.stdout + passed.stderr
                )

            run_path.write_text(json.dumps(trajectory(
                "", ["http://localhost:40016/"]
            )))
            failed = subprocess.run(command, capture_output=True, text=True)
            with self.subTest(index=index, case="no_op"):
                self.assertEqual(
                    failed.returncode, 1, failed.stdout + failed.stderr
                )

    def test_image_placeholder_and_fallbacks_are_safe(self):
        site_dir = Path(__file__).parents[1]
        placeholder = site_dir / "static" / "images" / "placeholder.svg"
        self.assertIn("<svg", placeholder.read_text())
        for template in (site_dir / "templates").glob("*.html"):
            with self.subTest(template=template.name):
                self.assertNotIn(
                    "parentElement.innerHTML", template.read_text()
                )


if __name__ == "__main__":
    unittest.main()
