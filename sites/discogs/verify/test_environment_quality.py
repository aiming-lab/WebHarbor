"""Static contract checks for the Discogs task and verifier bundle."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SITE_DIR.parents[1]
EXPECTED_KEYS = {
    "web_name",
    "id",
    "ques",
    "web",
    "upstream_url",
    "verifier_path",
    "judge_rubric",
}


class EnvironmentQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [
            json.loads(line)
            for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_task_count_never_drops_below_fifteen(self) -> None:
        self.assertGreaterEqual(len(self.rows), 15)

    def test_task_ids_schema_urls_and_verifier_paths_are_consistent(self) -> None:
        self.assertEqual(len(self.rows), len({row["id"] for row in self.rows}))
        for index, row in enumerate(self.rows):
            with self.subTest(task=index):
                self.assertEqual(EXPECTED_KEYS, set(row))
                self.assertEqual("Discogs", row["web_name"])
                self.assertEqual(f"Discogs--{index}", row["id"])
                self.assertEqual("http://localhost:40046/", row["web"])
                self.assertEqual("https://www.discogs.com/", row["upstream_url"])
                self.assertEqual(
                    f"sites/discogs/verify/verify_{index}.py",
                    row["verifier_path"],
                )
                self.assertTrue((REPO_ROOT / row["verifier_path"]).is_file())
                self.assertNotIn("answer", row)

    def test_rubrics_are_nonempty_rules_without_hidden_answer_keys(self) -> None:
        hidden_answers = {
            0: ("11:24", "RS 9242"),
            1: ("CP32-5244", "4:15"),
            2: ("UCCO-9038", "Joe Tarantino"),
            3: ("9732909", "8837214", "Dolby System", "Repress"),
            4: ("Colin Greenwood", "As The Waters Cover The Sea"),
            5: ("Kelly Blue", "kosmische", "8.27", "SMJ-6114", "SRS-6059"),
            6: ("Jeff Beck", "IGDA 1063/64"),
        }
        for index, row in enumerate(self.rows):
            with self.subTest(task=index):
                rubric = row["judge_rubric"]
                self.assertTrue(rubric.startswith("FACT CHECKPOINTS:"))
                self.assertIn("FAIL", rubric)
                for hidden in hidden_answers.get(index, ()):
                    if hidden.casefold() not in row["ques"].casefold():
                        self.assertNotIn(hidden.casefold(), rubric.casefold())


if __name__ == "__main__":
    unittest.main()
