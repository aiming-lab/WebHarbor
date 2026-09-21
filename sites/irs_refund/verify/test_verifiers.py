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
    answer_ok,
    evaluate,
)


def trajectory(answer, urls):
    return {
        "final_answer": answer,
        "steps": [
            {"step": number, "url": url}
            for number, url in enumerate(urls)
        ],
    }


def passing_urls(task_index):
    return [group[0] for group in NAV_ALTERNATIVES[task_index][0]]


def make_state_db(path, completed=False):
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, city TEXT, "
        "preferred_contact_method TEXT);"
        "INSERT INTO users VALUES "
        "(1, 'david.k@test.com', 'Seattle', 'Mail');"
    )
    if completed:
        connection.execute(
            "UPDATE users SET city='Spokane', preferred_contact_method='Email' "
            "WHERE email='david.k@test.com'"
        )
    connection.commit()
    connection.close()


class IRSRefundVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.initial_db = str(Path(cls.tmp.name) / "initial.db")
        cls.after_db = str(Path(cls.tmp.name) / "after.db")
        make_state_db(cls.initial_db)
        make_state_db(cls.after_db, completed=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, index, answer, urls, completed=True):
        return evaluate(
            index,
            trajectory(answer, urls),
            initial_db=self.initial_db,
            after_db=self.after_db if completed else self.initial_db,
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

    def test_stateful_claim_without_database_change_fails(self):
        result = self.verdict(
            8,
            PASS_ANSWERS[8],
            passing_urls(8),
            completed=False,
        )
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "profile_after_state")

    def test_identity_checklist_accepts_each_visible_option(self):
        answers = (
            "Confirm the synthetic photo ID name.",
            "Verify the stored mailing ZIP code.",
            "Review the preferred contact method.",
        )
        for answer in answers:
            with self.subTest(answer=answer):
                self.assertTrue(answer_ok(12, answer))

    def test_task_file_has_eighteen_grading_contracts(self):
        task_path = Path(__file__).parents[1] / "tasks.jsonl"
        rows = [json.loads(line) for line in task_path.read_text().splitlines()]
        self.assertEqual(len(rows), TASK_COUNT)
        auth_tasks = {6, 7, 8, 9, 16}
        for index, row in enumerate(rows):
            self.assertEqual(
                row.get("verifier_path"),
                f"sites/irs_refund/verify/verify_{index}.py",
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
                self.after_db,
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

    def test_only_expected_task_is_stateful(self):
        self.assertEqual(STATEFUL_TASKS, {8})


if __name__ == "__main__":
    unittest.main()
