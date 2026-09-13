"""Adversarial regression matrix for every Petfinder verifier."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode


VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
SEED_DB = SITE_DIR / "instance_seed/petfinder.db"
BASE_URL = "http://localhost:40026"
INQUIRY_MESSAGE = "I have a quiet home and would like to meet Nori."


def url(path: str, query: dict[str, str] | None = None) -> str:
    result = f"{BASE_URL}{path}"
    return f"{result}?{urlencode(query)}" if query else result


FILTERS = {
    0: {"species": "Dog", "location": "New York, NY", "age": "Adult", "size": "Large", "good_with_children": "1"},
    1: {"species": "Cat", "location": "Chicago, IL", "age": "Young", "size": "Small", "good_with_cats": "1"},
    2: {"species": "Rabbit", "location": "Seattle, WA", "age": "Adult", "size": "Small", "good_with_children": "1"},
    7: {"species": "Dog", "location": "Chicago, IL", "age": "Senior"},
}


ANSWERS = {
    0: "Milo Labrador Mix is at Hudson Valley Animal Rescue and has been on Petfinder for 3 days.",
    1: "Luna Domestic Shorthair is Female and is at PAWS Chicago.",
    2: "Nori Rabbit is at Seattle Animal Shelter. The adoption fee is $75.",
    3: "Nori is a Holland Lop Mix, Adult, in Seattle, WA.",
    4: "There are 2 favorite pets: Milo Labrador Mix and Nori Rabbit.",
    5: "Saved preferences: Chicago, IL and Newest pets first.",
    6: (
        "Choose a veterinarian and save the clinic number; "
        "Set up a quiet room with food, water, and a comfortable bed; "
        "Check fences, windows, plants, and household hazards."
    ),
    7: "Ollie Poodle Mix has fewer days: Ollie has 5 days and Maple has 18 days.",
    8: "Alice now has 3 favorite pets.",
    9: "The inquiry status is Submitted.",
}


PATHS = {
    0: [url("/pets", FILTERS[0]), url("/pets/milo-labrador-mix")],
    1: [url("/pets", FILTERS[1]), url("/pets/luna-domestic-shorthair")],
    2: [url("/pets", FILTERS[2]), url("/pets/nori-rabbit")],
    3: [url("/search", {"q": "Nori"}), url("/pets/nori-rabbit")],
    4: [url("/login"), url("/account")],
    5: [url("/login"), url("/account"), url("/account")],
    6: [url("/guides/pet-adoption-checklist")],
    7: [url("/pets", FILTERS[7]), url("/pets/maple-senior-beagle"), url("/pets/ollie-poodle-mix")],
    8: [url("/login"), url("/search", {"q": "Luna"}), url("/pets/luna-domestic-shorthair"), url("/account")],
    9: [url("/login"), url("/search", {"q": "Nori"}), url("/pets/nori-rabbit"), url("/account")],
}


def trajectory(index: int, answer: str | None = None, paths: list[str] | None = None) -> dict:
    observed_paths = PATHS[index] if paths is None else paths
    steps = [{"url": path, "action": "navigate", "params": {}} for path in observed_paths]
    if index == 9 and observed_paths:
        detail_index = next(
            (position for position, path in enumerate(observed_paths) if path.startswith(url("/pets/nori-rabbit"))),
            None,
        )
        if detail_index is not None:
            steps.insert(
                detail_index + 1,
                {
                    "url": url("/pets/nori-rabbit"),
                    "action": "input",
                    "params": {"text": INQUIRY_MESSAGE},
                },
            )
    return {
        "task_id": f"Petfinder--{index}",
        "start_url": f"{BASE_URL}/",
        "steps": steps,
        "final_url": observed_paths[-1] if observed_paths else f"{BASE_URL}/",
        "final_answer": ANSWERS[index] if answer is None else answer,
    }


class VerifierMatrixTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="petfinder-verifier-test-")
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def databases(self, index: int, mutate: bool) -> tuple[Path, Path]:
        initial = self.root / f"initial-{index}.db"
        after = self.root / f"after-{index}.db"
        shutil.copyfile(SEED_DB, initial)
        shutil.copyfile(SEED_DB, after)
        if mutate:
            connection = sqlite3.connect(after)
            try:
                if index == 5:
                    connection.execute(
                        "UPDATE user SET home_location=?, sort_preference=? WHERE lower(email)=lower(?)",
                        ("Chicago, IL", "Newest pets first", "alice.j@test.com"),
                    )
                elif index == 8:
                    connection.execute(
                        "INSERT INTO saved_item(user_id, listing_id) "
                        "SELECT u.id,l.id FROM user u,listing l "
                        "WHERE lower(u.email)=lower(?) AND l.slug=?",
                        ("alice.j@test.com", "luna-domestic-shorthair"),
                    )
                elif index == 9:
                    connection.execute(
                        "INSERT INTO inquiry(user_id, listing_id, message, status) "
                        "SELECT u.id,l.id,?,? FROM user u,listing l "
                        "WHERE lower(u.email)=lower(?) AND l.slug=?",
                        (INQUIRY_MESSAGE, "Submitted", "alice.j@test.com", "nori-rabbit"),
                    )
                connection.commit()
            finally:
                connection.close()
        return initial, after

    def verify(self, index: int, observed: dict, mutate: bool = False) -> tuple[subprocess.CompletedProcess[str], dict]:
        run_dir = self.root / f"run-{index}-{len(list(self.root.glob('run-*')))}"
        run_dir.mkdir()
        (run_dir / "trajectory.json").write_text(json.dumps(observed), encoding="utf-8")
        initial, after = self.databases(index, mutate)
        result = subprocess.run(
            [
                sys.executable,
                str(VERIFY_DIR / f"verify_{index}.py"),
                "--run_dir",
                str(run_dir),
                "--initial_db",
                str(initial),
                "--after_db",
                str(after),
                "--no_llm",
                "true",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        return result, payload

    def assert_passes(self, index: int, observed: dict, mutate: bool = False):
        result, payload = self.verify(index, observed, mutate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["pass"], payload)

    def assert_fails(self, index: int, observed: dict, mutate: bool = False):
        result, payload = self.verify(index, observed, mutate)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(payload["pass"], payload)

    def test_positive_examples_pass(self):
        for index in range(10):
            with self.subTest(index=index):
                self.assert_passes(index, trajectory(index), mutate=index in {5, 8, 9})

    def test_noop_examples_fail(self):
        for index in range(10):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, answer="No action taken.", paths=[]))

    def test_right_answer_without_required_navigation_fails(self):
        for index in range(10):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, paths=[]), mutate=index in {5, 8, 9})

    def test_wrong_answer_after_valid_path_fails(self):
        for index in range(10):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, answer="The requested facts were not found."), mutate=index in {5, 8, 9})

    def test_state_tasks_reject_claims_without_persisted_change(self):
        for index in (5, 8, 9):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index), mutate=False)

    def test_save_task_accepts_signed_out_then_login_alternate_path(self):
        alternate_paths = [
            url("/search", {"q": "Luna"}),
            url("/pets/luna-domestic-shorthair"),
            url("/login", {"next": "/pets/luna-domestic-shorthair"}),
            url("/pets/luna-domestic-shorthair"),
            url("/account"),
        ]
        self.assert_passes(8, trajectory(8, paths=alternate_paths), mutate=True)


if __name__ == "__main__":
    unittest.main()
