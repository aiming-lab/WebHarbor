import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from answer_checks import answer_ok
from navigation import navigation_ok
from state_checks import state_ok
from test_verifiers import make_state_db, passing_urls, trajectory
from verify_lib import PASS_ANSWERS


class ReviewRegressions(unittest.TestCase):
    def test_wrong_fact_bindings(self):
        cases = [
            (3, "Bitcoin high $110,249.89; low $299,489.06."),
            (7, "Jun 2026 revenue $98.36 million; net profit margin 22.77%."),
            (13, "LMT is lowest at 16.47; HON 22.45; RTX 26.97."),
            (10, "NVIDIA did not fall -18.57%; it rose 10%."),
            (
                6,
                "Intel is Buy, 5 ratings, average target $200. Ignore obsolete references: Hold, 14, 104.21.",
            ),
            (3, "High $299,489.06; low $110,249.89; high $300,000."),
            (3, "The high is not $299,489.06. The low is $110,249.89."),
            (7, "Jun 2026 revenue $98.36B; margin 22.77 dollars."),
            (13, "HON 16.47; LMT 22.45; RTX 26.97. RTX is lowest."),
        ]
        for index, answer in cases:
            with self.subTest(index=index, answer=answer):
                self.assertFalse(answer_ok(index, answer))

    def test_equivalent_natural_answers(self):
        cases = [
            (1, "Ex-dividend date: 2026-10-04. Quarterly dividend: $0.44."),
            (1, "Ex-dividend date: 4 October 2026. Quarterly dividend: 0.44 dollars."),
            (
                7,
                "For June 2026, revenue was $98.36 billion and net profit margin was 22.77%.",
            ),
            (9, "2025 revenue: $182,600,000,000."),
            (
                18,
                "Growth ideas total gain is 33.23%; NVIDIA has the largest gain, at 121.64%.",
            ),
            (14, "F has the lowest P/E among the five most active stocks, at 32.19."),
            (10, "NVIDIA fell 18.57% over one year."),
            (3, "| Metric | USD |\n| High | $299,489.06 |\n| Low | $110,249.89 |"),
            (
                13,
                "Honeywell is lowest.\n| Company | P/E |\n| HON | 16.47 |\n| LMT | 22.45 |\n| RTX | 26.97 |",
            ),
            (3, "The high is $299,489.06, not $300,000; the low is $110,249.89."),
        ]
        for index, answer in cases:
            with self.subTest(index=index, answer=answer):
                self.assertTrue(answer_ok(index, answer))

    def test_navigation_binding_and_origin(self):
        cases = [
            (10, ["/quote/NVDA:NASDAQ", "/quote/KO:NYSE?range=1Y"]),
            (13, ["/?unused=/compare,lmt,rtx,hon"]),
            (3, ["https://unrelated.invalid/quote/BTC-USD"]),
            (3, ["/quote/BTC-USD-FAKE"]),
            (7, ["/quote/GOOGL:NASDAQ?tab=financials&period=annual"]),
            (8, ["/quote/WMT:NASDAQ?tab=financials&statement=income"]),
            (10, ["/quote/NVDA:NASDAQ?range=1Y&range=1D"]),
            (13, ["/compare?tickers=LMT,RTX,HONEYWELLFAKE"]),
        ]
        for index, urls in cases:
            with self.subTest(index=index, urls=urls):
                self.assertFalse(
                    navigation_ok(index, trajectory(PASS_ANSWERS[index], urls))[0]
                )
        t = trajectory(PASS_ANSWERS[10], [])
        t["steps"] = [
            {
                "url": "http://localhost:40016/",
                "url_after": "http://localhost:40016/quote/NVDA:NASDAQ?range=1Y",
            }
        ]
        self.assertTrue(navigation_ok(10, t)[0])

    def test_saved_state_and_unrelated_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            initial, after = run / "initial_state.db", run / "after_state.db"
            make_state_db(initial)
            make_state_db(after, completed=True)
            self.assertTrue(state_ok(initial, after)[0])
            for sql in [
                "DELETE FROM portfolio_lots WHERE id=1; DELETE FROM portfolios WHERE id=2;",
                "UPDATE portfolios SET cash=0 WHERE id=1;",
                "UPDATE users SET email='different@test.com' WHERE id=2;",
                "UPDATE portfolio_lots SET shares=26 WHERE id=2;",
                'INSERT INTO portfolios VALUES (4, 2, "Extra", 10);',
            ]:
                altered = run / "altered.db"
                shutil.copy2(after, altered)
                with sqlite3.connect(altered) as db:
                    db.executescript(sql)
                with self.subTest(sql=sql):
                    self.assertFalse(state_ok(initial, altered)[0])
            t = trajectory(PASS_ANSWERS[19], passing_urls(19))
            (run / "trajectory.json").write_text(json.dumps(t))
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("verify_19.py")),
                    "--run_dir",
                    str(run),
                    "--container",
                    "nonexistent-test-container",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after.unlink()
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("verify_19.py")),
                    "--run_dir",
                    str(run),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(
                after.exists(), "Read-only grading must not create missing DBs"
            )

    def test_rubrics_do_not_publish_reference_facts(self):
        rows = [
            json.loads(line)
            for line in (Path(__file__).parents[1] / "tasks.jsonl")
            .read_text()
            .splitlines()
        ]
        for row in rows:
            rubric = row["judge_rubric"]
            for secret in (
                "187,092",
                "98.36",
                "33.23",
                "121.64",
                "Marathon Petroleum",
                "Realty Income",
                "South China Morning Post",
            ):
                self.assertNotIn(secret, rubric)
