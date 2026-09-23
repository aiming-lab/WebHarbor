import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_lib import (
    PASS_ANSWERS,
    TASK_COUNT,
    evaluate,
)


def trajectory(answer, urls):
    return {
        "start_url": "http://localhost:40016/",
        "final_answer": answer,
        "steps": [{"step": n, "url": url} for n, url in enumerate(urls)],
    }


def passing_urls(index):
    paths = {
        0: ["/?region=latam", "/quote/IBOV:INDEXBVMF"],
        1: ["/quote/KO:NYSE"],
        2: ["/quote/NVDA:NASDAQ?range=1Y"],
        3: ["/quote/BTC-USD"],
        4: ["/currency-converter?amount=2500&from=USD&to=JPY"],
        5: [
            "/quote/BA:NYSE",
            "/news/ba-boeing-co-outlines-a-multi-year-efficiency-plan-at-its-investor-day",
        ],
        6: ["/quote/INTC:NASDAQ?tab=analysis"],
        7: ["/quote/GOOGL:NASDAQ?tab=financials"],
        8: ["/quote/WMT:NASDAQ?tab=financials&statement=balance"],
        9: ["/quote/CVX:NYSE?tab=financials&period=annual"],
        10: ["/quote/NVDA:NASDAQ?range=1Y"],
        11: ["/quote/XLE:NYSEARCA?tab=holdings"],
        12: ["/quote/MSFT:NASDAQ?tab=earnings"],
        13: ["/compare?tickers=LMT,RTX,HON"],
        14: [
            "/markets/most-active",
            "/quote/INTC:NASDAQ",
            "/quote/NVDA:NASDAQ",
            "/quote/T:NYSE",
            "/quote/TSLA:NASDAQ",
            "/quote/F:NYSE",
        ],
        15: [
            "/markets/climate-leaders",
            "/quote/NVDA:NASDAQ",
            "/quote/AAPL:NASDAQ",
            "/quote/MSFT:NASDAQ",
            "/quote/GOOGL:NASDAQ",
            "/quote/V:NYSE",
            "/quote/MA:NYSE",
        ],
        16: [
            "/search?q=utility",
            "/quote/AEP:NASDAQ",
            "/quote/D:NYSE",
            "/quote/DUK:NYSE",
            "/quote/EXC:NASDAQ",
            "/quote/NEE:NYSE",
            "/quote/SO:NYSE",
        ],
        17: [
            "/login",
            "/lists/2",
            "/quote/KO:NYSE",
            "/quote/PG:NYSE",
            "/quote/XOM:NYSE",
            "/quote/DUK:NYSE",
            "/quote/O:NYSE",
            "/quote/VZ:NYSE",
        ],
        18: ["/login", "/portfolios/2"],
        19: ["/login", "/portfolios/3"],
    }
    return ["http://localhost:40016" + path for path in paths[index]]


def make_state_db(path, completed=False):
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);"
        "CREATE TABLE portfolios (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "name TEXT, cash REAL);"
        "CREATE TABLE instruments (id INTEGER PRIMARY KEY, ticker TEXT);"
        "CREATE TABLE portfolio_lots (id INTEGER PRIMARY KEY, "
        "portfolio_id INTEGER, instrument_id INTEGER, shares REAL, "
        "cost_basis REAL);"
        "INSERT INTO users VALUES (1, 'alice.j@test.com');"
        "INSERT INTO instruments VALUES (1, 'JPM');"
        "INSERT INTO users VALUES (2, 'bob@test.com');"
        "INSERT INTO portfolios VALUES (1, 1, 'Existing Alice', 100);"
        "INSERT INTO portfolios VALUES (2, 2, 'Existing Bob', 200);"
        "INSERT INTO portfolio_lots VALUES (1, 2, 1, 10, 250);"
    )
    if completed:
        connection.executescript(
            "INSERT INTO portfolios VALUES (3, 1, 'Bank basket', 5000.0);"
            "INSERT INTO portfolio_lots VALUES (2, 3, 1, 25.0, 300.0);"
        )
    connection.commit()
    connection.close()


class GoogleFinanceVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.initial_db = str(Path(cls.tmp.name) / "initial.db")
        cls.after_db = str(Path(cls.tmp.name) / "after.db")
        make_state_db(cls.initial_db, completed=False)
        make_state_db(cls.after_db, completed=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, index, answer, urls, completed=True):
        after = self.after_db if completed else self.initial_db
        return evaluate(
            index,
            trajectory(answer, urls),
            initial_db=self.initial_db,
            after_db=after,
        )

    def test_all_twenty_pass_cases(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, PASS_ANSWERS[index], passing_urls(index))
                self.assertTrue(result["pass"], result)

    def test_all_twenty_no_op_runs_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(index, "", ["http://localhost:40016/"])
                self.assertFalse(result["pass"], result)

    def test_all_twenty_prior_knowledge_shortcuts_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    PASS_ANSWERS[index],
                    ["http://localhost:40016/"],
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], "required_navigation")

    def test_all_twenty_wrong_answers_fail(self):
        for index in range(TASK_COUNT):
            with self.subTest(index=index):
                result = self.verdict(
                    index,
                    "This is definitely the wrong answer.",
                    passing_urls(index),
                )
                self.assertFalse(result["pass"], result)
                self.assertEqual(result["reason"], "frozen_answer")

    def test_portfolio_claim_without_database_state_fails(self):
        result = self.verdict(19, PASS_ANSWERS[19], passing_urls(19), completed=False)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "portfolio_after_state")

    def test_task_file_has_twenty_grading_contracts(self):
        task_path = Path(__file__).parents[1] / "tasks.jsonl"
        rows = [json.loads(line) for line in task_path.read_text().splitlines()]
        self.assertEqual(len(rows), TASK_COUNT)
        for index, row in enumerate(rows):
            self.assertEqual(
                row.get("verifier_path"),
                f"sites/google_finance/verify/verify_{index}.py",
            )
            self.assertTrue(row.get("judge_rubric", "").startswith("FACT CHECKPOINTS:"))
            self.assertNotIn("answer", row)
            self.assertTrue((Path(__file__).parent / f"verify_{index}.py").exists())

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

            run_path.write_text(
                json.dumps(trajectory(PASS_ANSWERS[index], passing_urls(index)))
            )
            passed = subprocess.run(command, capture_output=True, text=True)
            with self.subTest(index=index, case="pass"):
                self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

            run_path.write_text(json.dumps(trajectory("", ["http://localhost:40016/"])))
            failed = subprocess.run(command, capture_output=True, text=True)
            with self.subTest(index=index, case="no_op"):
                self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()
