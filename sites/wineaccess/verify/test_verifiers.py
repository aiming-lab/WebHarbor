import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_lib import NAV_ALTERNATIVES, PASS_ANSWERS, STATEFUL_TASKS, TASK_COUNT, evaluate


def trajectory(answer, urls):
    return {"final_answer": answer, "steps": [{"step": i, "url": url} for i, url in enumerate(urls)]}


def passing_urls(index):
    return [group[0] for group in NAV_ALTERNATIVES[index][0]]


def apply_state(index, path):
    with sqlite3.connect(path) as db:
        uid = db.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]
        if index == 0:
            db.execute("INSERT INTO cart_items(user_id,wine_id,quantity) VALUES(?,?,?)", (uid, 38, 1))
        elif index == 1:
            db.execute("INSERT INTO wishlist_items(user_id,wine_id,note) VALUES(?,?,?)", (uid, 18, ""))
        elif index == 4:
            db.execute("INSERT INTO cart_items(user_id,wine_id,quantity) VALUES(?,?,?)", (uid, 36, 1))
        elif index == 5:
            db.execute("UPDATE users SET favorite_variety='Pinot Noir' WHERE id=?", (uid,))
        elif index == 7:
            db.execute("INSERT INTO cart_items(user_id,wine_id,quantity) VALUES(?,?,?)", (uid, 33, 2))
        elif index == 10:
            carol = db.execute("SELECT id FROM users WHERE email='carol.d@test.com'").fetchone()[0]
            club = db.execute("SELECT id FROM clubs WHERE slug='connoisseurs'").fetchone()[0]
            db.execute("INSERT INTO club_memberships(user_id,club_id,status) VALUES(?,?,?)", (carol, club, "Active"))
        elif index == 13:
            db.execute("INSERT INTO users(id,username,email,password_hash,display_name) VALUES(99,'new-reviewer','new-reviewer@example.com','hash','New Reviewer')")
            db.execute("INSERT INTO cart_items(user_id,wine_id,quantity) VALUES(99,2,1)")
        elif index == 14:
            david = db.execute("SELECT id FROM users WHERE email='david.k@test.com'").fetchone()[0]
            item = db.execute("SELECT id FROM cart_items WHERE user_id=? ORDER BY id LIMIT 1", (david,)).fetchone()[0]
            db.execute("DELETE FROM cart_items WHERE id=?", (item,))
        elif index == 16:
            db.execute("INSERT INTO orders(id,user_id,order_number,status) VALUES(99,?,'WA-260817-1005','Processing')", (uid,))
            db.execute("DELETE FROM cart_items WHERE user_id=?", (uid,))
        db.commit()


class WineAccessVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.seed = Path(__file__).parents[1] / "instance_seed" / "wineaccess.db"
        cls.after = {}
        for index in STATEFUL_TASKS:
            path = Path(cls.tmp.name) / f"after-{index}.db"
            shutil.copy2(cls.seed, path)
            apply_state(index, path)
            cls.after[index] = path

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, index, answer, urls, changed=True):
        return evaluate(index, trajectory(answer, urls), str(self.seed), str(self.after[index] if changed and index in STATEFUL_TASKS else self.seed))

    def test_all_eighteen_positive_cases(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                self.assertTrue(self.verdict(index, PASS_ANSWERS[index], passing_urls(index))["pass"])

    def test_all_eighteen_no_op_runs_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                self.assertFalse(self.verdict(index, "", ["http://localhost:40015/"])["pass"])

    def test_all_eighteen_prior_knowledge_shortcuts_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, PASS_ANSWERS[index], ["http://localhost:40015/"])
                self.assertFalse(result["pass"])
                self.assertEqual(result["reason"], "required_navigation")

    def test_all_eighteen_wrong_answers_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, "Definitely wrong.", passing_urls(index))
                self.assertFalse(result["pass"])
                self.assertEqual(result["reason"], "frozen_answer")

    def test_all_stateful_claims_require_database_change(self):
        for index in sorted(STATEFUL_TASKS):
            with self.subTest(index=index):
                result = self.verdict(index, PASS_ANSWERS[index], passing_urls(index), changed=False)
                self.assertFalse(result["pass"])

    def test_task_file_has_exact_grading_contracts_and_credentials(self):
        path = Path(__file__).parents[1] / "tasks.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), TASK_COUNT)
        auth = {0, 1, 4, 5, 6, 7, 10, 14, 16}
        for index, row in enumerate(rows):
            self.assertEqual(row.get("verifier_path"), f"sites/wineaccess/verify/verify_{index}.py")
            self.assertIn("NAVIGATION:", row.get("judge_rubric", ""))
            self.assertNotIn("answer", row)
            self.assertEqual(row["web"], "http://localhost:40016/")
            self.assertTrue((Path(__file__).parent / f"verify_{index}.py").exists())
            if index in auth:
                self.assertIn("TestPass123!", row["ques"])

    def test_all_wrapper_exit_codes(self):
        verify = Path(__file__).parent
        for index in range(TASK_COUNT):
            run_dir = Path(self.tmp.name) / f"run-{index}"
            run_dir.mkdir()
            run = run_dir / "trajectory.json"
            command = [sys.executable, str(verify / f"verify_{index}.py"), "--run_dir", str(run_dir), "--initial_db", str(self.seed), "--after_db", str(self.after.get(index, self.seed))]
            run.write_text(json.dumps(trajectory(PASS_ANSWERS[index], passing_urls(index))))
            passed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            run.write_text(json.dumps(trajectory("", ["http://localhost:40015/"])))
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()
