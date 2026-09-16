"""The tasks.jsonl contract, and the rule that no rubric carries a ground-truth value.

``sites/berkeley/tasks.jsonl`` is agent-facing: the rubric may state *rules* but
must not contain any value the verifiers derive from the snapshot. This module
re-derives every target and asserts that no derived phrase, number or
distinctive token appears in the rubrics — unless the task text itself already
names it (then it is not a leak).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import SITE_DIR, SEED_DB  # noqa: E402

VERIFY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY_DIR))

import ground_truth  # noqa: E402

TASKS = SITE_DIR / "tasks.jsonl"
EXPECTED_KEYS = {"web_name", "id", "ques", "web", "upstream_url", "verifier_path", "judge_rubric"}
EXPECTED_IDS = [1, 2, 4, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 27, 28, 30, 31]

# Tokens that appear across many derived values are domain vocabulary, not answers.
GENERIC_TASK_FREQUENCY = 4


def load_rows() -> list[dict]:
    return [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]


def strings_in(value) -> list[str]:
    """Every string (and numeric) literal inside a derived fact, recursively."""
    found: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            found.extend(strings_in(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(strings_in(item))
    elif isinstance(value, bool):
        pass
    elif isinstance(value, (int, float)):
        found.append(f"{value:g}")
    elif isinstance(value, str):
        found.append(value)
    return found


# Long prose (programme/article descriptions) is rendered on the page but is not
# an answer value; only short labels and names are treated as leak candidates.
MAX_VALUE_LENGTH = 100
MAX_VALUE_TOKENS = 10


def answer_values(facts: dict) -> list[str]:
    return [
        value for value in strings_in({key: value for key, value in facts.items() if key != "task"})
        if len(value.strip()) <= MAX_VALUE_LENGTH and len(value.split()) <= MAX_VALUE_TOKENS
    ]


def forbidden_for(facts: dict, ques: str, generic_tokens: set[str]) -> set[str]:
    """Phrases, numbers and distinctive tokens that must not appear in the rubric.

    Anything the task text itself names is not a leak; tokens are compared with a
    crude stem rule so "requirement" matches the task's "requirements".
    """
    values = answer_values(facts)
    lowered_ques = ques.lower()
    ques_tokens = set(re.findall(r"[a-z]{4,}", lowered_ques))

    def in_ques_token(token: str) -> bool:
        return any(token == other or token.startswith(other) or other.startswith(token)
                   for other in ques_tokens)

    phrases = {
        value.strip().lower() for value in values
        if len(value.strip()) >= 4 and value.strip().lower() not in lowered_ques
    }
    numbers = {number_text for value in values for number_text in re.findall(r"\d+(?:\.\d+)?", value)}
    tokens = {token for value in values for token in re.findall(r"[a-z]{4,}", value.lower())}
    return phrases | numbers | {
        token for token in tokens if not in_ques_token(token) and token not in generic_tokens
    }


def leaks_in(rubric: str, forbidden: set[str]) -> list[str]:
    """Forbidden phrases/numbers anywhere; single tokens only as whole words."""
    lowered = rubric.lower()
    found = []
    for value in sorted(forbidden):
        if len(value) < 4:
            continue
        if re.fullmatch(r"[a-z]+", value):
            if re.search(rf"\b{re.escape(value)}\b", lowered):
                found.append(value)
        elif value in lowered:
            found.append(value)
    return found


def generic_vocabulary(all_facts: dict[int, dict]) -> set[str]:
    """Tokens that recur across many tasks are domain vocabulary, not answers."""
    per_task = {
        number: {
            token
            for value in answer_values(facts)
            for token in re.findall(r"[a-z]{4,}", value.lower())
        }
        for number, facts in all_facts.items()
    }
    counts: dict[str, int] = {}
    for tokens in per_task.values():
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return {token for token, count in counts.items() if count >= GENERIC_TASK_FREQUENCY}


class TaskFileContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = load_rows()
        self.facts = ground_truth.all_ground_truth(str(SEED_DB))
        self.generic_tokens = generic_vocabulary(self.facts)

    def test_row_count_ids_and_keys(self) -> None:
        self.assertEqual(len(self.rows), 22)
        self.assertEqual(
            [int(row["id"].rsplit("--", 1)[1]) for row in self.rows], EXPECTED_IDS
        )
        for row in self.rows:
            self.assertEqual(set(row), EXPECTED_KEYS, row["id"])
            self.assertEqual(row["web_name"], "UC Berkeley")
            self.assertEqual(row["web"], "http://localhost:40029/")
            self.assertEqual(row["upstream_url"], "https://www.berkeley.edu/")
            self.assertTrue(row["ques"].strip())
            self.assertIn("Checkpoints:", row["judge_rubric"])

    def test_verifier_paths_exist_and_match_the_task_id(self) -> None:
        for row in self.rows:
            number = int(row["id"].rsplit("--", 1)[1])
            path = Path(row["verifier_path"])
            self.assertFalse(path.is_absolute(), row["id"])
            self.assertEqual(path.name, f"verify_{number}.py")
            full = SITE_DIR.parents[1] / path
            self.assertTrue(full.is_file(), f"{row['id']}: missing {full}")
            self.assertIn(f'TASK_ID = "UC Berkeley--{number}"', full.read_text(encoding="utf-8"))

    def test_every_verifier_file_is_referenced(self) -> None:
        referenced = {Path(row["verifier_path"]).name for row in self.rows}
        present = {path.name for path in (SITE_DIR / "verify").glob("verify_[0-9]*.py")}
        self.assertEqual(referenced, present)

    def test_rubrics_are_unique(self) -> None:
        rubrics = [row["judge_rubric"] for row in self.rows]
        self.assertEqual(len(set(rubrics)), len(rubrics))

    def test_no_rubric_contains_a_derived_ground_truth_value(self) -> None:
        # The shared preamble is identical boilerplate across every row; the scan
        # covers each row's own checkpoints, where a task-specific value would
        # actually leak.
        rubrics = [row["judge_rubric"] for row in self.rows]
        preamble = os.path.commonprefix(rubrics)
        for row in self.rows:
            number = int(row["id"].rsplit("--", 1)[1])
            forbidden = forbidden_for(self.facts[number], row["ques"], self.generic_tokens)
            leaked = leaks_in(row["judge_rubric"][len(preamble):], forbidden)
            self.assertEqual(leaked, [], f"{row['id']} rubric leaks derived values: {leaked}")

    def test_leak_detector_has_teeth(self) -> None:
        """The scan must reject a rubric that carries the derived answer."""
        row = next(row for row in self.rows if row["id"] == "UC Berkeley--4")
        forbidden = forbidden_for(self.facts[4], row["ques"], self.generic_tokens)
        self.assertTrue(forbidden)
        self.assertTrue(
            leaks_in("the answer must name Jennifer Doudna and the National Medal of Science", forbidden)
        )
        self.assertEqual(
            leaks_in("the article's page must have been opened and the award it reports given", forbidden),
            [],
        )

    def test_no_rubric_contains_a_derived_number(self) -> None:
        for row in self.rows:
            number = int(row["id"].rsplit("--", 1)[1])
            rubric = row["judge_rubric"]
            numbers = {
                found
                for value in strings_in({k: v for k, v in self.facts[number].items() if k != "task"})
                for found in re.findall(r"\d+(?:\.\d+)?", value)
            }
            ques_numbers = set(re.findall(r"\d+(?:\.\d+)?", row["ques"]))
            for value in sorted(numbers - ques_numbers):
                self.assertIsNone(
                    re.search(rf"(?<![\d.]){re.escape(value)}(?![\d.])", rubric),
                    f"{row['id']} rubric repeats the derived number {value!r}",
                )

    def test_bookmark_rows_are_empty_in_the_seed(self) -> None:
        """--30/--31 assume an empty bookmarks table (see VERIFIER_PLAN.md B.2)."""
        worker = sqlite3.connect(str(SEED_DB))
        try:
            count = worker.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        finally:
            worker.close()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
