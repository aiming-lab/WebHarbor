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
BASE_URL = "http://localhost:40029"
INQUIRY_MESSAGE = "I have a quiet home and would like to meet Nori."


def url(path: str, query: dict[str, str] | None = None) -> str:
    result = f"{BASE_URL}{path}"
    return f"{result}?{urlencode(query)}" if query else result


FILTERS = {
    0: {"species": "Dog", "location": "New York, NY", "age": "Adult", "size": "Large", "good_with_children": "1"},
    1: {"species": "Cat", "location": "Chicago, IL", "age": "Young", "size": "Small", "good_with_cats": "1"},
    2: {"species": "Rabbit", "location": "Seattle, WA", "age": "Adult", "size": "Small", "good_with_children": "1"},
    7: {"species": "Dog", "location": "Chicago, IL", "age": "Senior"},
    10: {"species": "Dog", "location": "Boston, MA", "age": "Young", "good_with_dogs": "1"},
    11: {"species": "Dog", "sort": "name", "page": "2"},
}


ANSWERS = {
    0: "Milo Labrador Mix is at Hudson Valley Animal Rescue and has been on Petfinder for 3 days.",
    1: "Luna Domestic Shorthair is Female and is at PAWS Chicago.",
    2: "Nori Rabbit is at Seattle Animal Shelter. The adoption fee is $75.",
    3: "Nori's adoption fee is $75, her coat is Short, and her shelter is Seattle Animal Shelter.",
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
    10: "Scout Border Collie has the lowest fee at $300; Ace Whippet is $335 and Phoebe Samoyed is $410.",
    11: "The first pet on page 2 is Leo Vizsla Mix, a Vizsla Mix at Love-A-Bull.",
    12: "Mochi Siamese Mix has a $185 adoption fee, a Short coat, and Lynx Point coloring.",
    13: (
        "Set up a rabbit-friendly space: Offer unlimited grass hay; "
        "Cover cords and unsafe baseboards; Include a hide box and non-slip flooring."
    ),
    14: "Milo Labrador Mix was already in favorites, so the total remains 2 favorite pets.",
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
    10: [
        url("/pets", FILTERS[10]),
        url("/pets/scout-border-collie"),
        url("/pets/ace-whippet"),
        url("/pets/phoebe-samoyed"),
    ],
    11: [url("/pets", FILTERS[11]), url("/pets/leo-vizsla-mix")],
    12: [
        url("/search", {"q": "Seattle Humane", "location": "Seattle, WA"}),
        url("/pets/mochi-siamese-mix"),
    ],
    13: [url("/search", {"q": "rabbit housing"}), url("/guides/rabbit-housing-essentials")],
    14: [url("/login"), url("/search", {"q": "Milo"}), url("/pets/milo-labrador-mix"), url("/account")],
}


def trajectory(index: int, answer: str | None = None, paths: list[str] | None = None) -> dict:
    observed_paths = PATHS[index] if paths is None else paths
    steps = [{"url": path, "action": "navigate", "params": {}} for path in observed_paths]
    if index in {4, 5, 8, 9, 14} and observed_paths:
        login_index = next(
            (position for position, path in enumerate(observed_paths) if path.startswith(url("/login"))),
            None,
        )
        if login_index is not None:
            steps[login_index + 1:login_index + 1] = [
                {"url": observed_paths[login_index], "action": "input", "params": {"text": "alice.j@test.com"}},
                {"url": observed_paths[login_index], "action": "input", "params": {"text": "[TEST_PASSWORD_FROM_TASK]"}},
            ]
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
    if index == 14 and observed_paths:
        detail_index = next(
            (position for position, path in enumerate(observed_paths) if path.startswith(url("/pets/milo-labrador-mix"))),
            None,
        )
        if detail_index is not None:
            steps.insert(
                detail_index + 1,
                {
                    "url": url("/pets/milo-labrador-mix"),
                    "action": "click",
                    "params": {"locator": "role=button name~=Save this pet"},
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

    def verify(
        self,
        index: int,
        observed: dict | str,
        mutate: bool = False,
        extra_sql: tuple[str, tuple] | None = None,
        baseline_sql: tuple[str, tuple] | None = None,
        remove_after: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        run_dir = self.root / f"run-{index}-{len(list(self.root.glob('run-*')))}"
        run_dir.mkdir()
        encoded = observed if isinstance(observed, str) else json.dumps(observed)
        (run_dir / "trajectory.json").write_text(encoded, encoding="utf-8")
        initial, after = self.databases(index, mutate)
        if baseline_sql:
            for database in (initial, after):
                connection = sqlite3.connect(database)
                try:
                    connection.execute(*baseline_sql)
                    connection.commit()
                finally:
                    connection.close()
        if extra_sql:
            connection = sqlite3.connect(after)
            try:
                connection.execute(*extra_sql)
                connection.commit()
            finally:
                connection.close()
        if remove_after:
            after.unlink()
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
        for index in range(15):
            with self.subTest(index=index):
                self.assert_passes(index, trajectory(index), mutate=index in {5, 8, 9})

    def test_noop_examples_fail(self):
        for index in range(15):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, answer="No action taken.", paths=[]))

    def test_right_answer_without_required_navigation_fails(self):
        for index in range(15):
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, paths=[]), mutate=index in {5, 8, 9})

    def test_wrong_answer_after_valid_path_fails(self):
        for index in range(15):
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

    def test_legal_paraphrase_passes(self):
        answer = "With only 5 days, Ollie Poodle Mix has been listed for fewer days than Maple, which has 18 days."
        self.assert_passes(7, trajectory(7, answer=answer))

    def test_negated_ground_truth_fails(self):
        answer = "Milo Labrador Mix is not at Hudson Valley Animal Rescue and has not been listed for 3 days."
        self.assert_fails(0, trajectory(0, answer=answer))

    def test_state_tasks_reject_same_table_side_effects(self):
        extras = {
            5: (
                "UPDATE user SET home_location=? WHERE lower(email)=lower(?)",
                ("Boston, MA", "bob.c@test.com"),
            ),
            8: (
                "INSERT INTO saved_item(user_id, listing_id) "
                "SELECT u.id,l.id FROM user u,listing l WHERE lower(u.email)=lower(?) AND l.slug=?",
                ("bob.c@test.com", "poppy-tabby"),
            ),
            9: (
                "INSERT INTO inquiry(user_id, listing_id, message, status) "
                "SELECT u.id,l.id,?,? FROM user u,listing l WHERE lower(u.email)=lower(?) AND l.slug=?",
                ("Unrequested inquiry", "Submitted", "bob.c@test.com", "luna-domestic-shorthair"),
            ),
        }
        for index, statement in extras.items():
            with self.subTest(index=index):
                result, payload = self.verify(index, trajectory(index), mutate=True, extra_sql=statement)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(payload["pass"], payload)

    def test_missing_after_snapshot_fails_without_traceback(self):
        result, payload = self.verify(8, trajectory(8), mutate=True, remove_after=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(payload["pass"], payload)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_trajectory_fails_as_structured_json(self):
        result, payload = self.verify(0, "{not-json")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(payload["pass"], payload)
        self.assertEqual(payload["reason"], "verifier_input_valid")
        self.assertNotIn("Traceback", result.stderr)

    def test_wrong_task_replay_and_foreign_origin_fail(self):
        replay = trajectory(0)
        replay["task_id"] = "Petfinder--1"
        self.assert_fails(0, replay)

        foreign = trajectory(3)
        for step in foreign["steps"]:
            step["url"] = step["url"].replace(BASE_URL, "https://example.invalid")
        foreign["final_url"] = foreign["final_url"].replace(BASE_URL, "https://example.invalid")
        self.assert_fails(3, foreign)

    def test_truncated_navigation_and_wrong_numeric_binding_fail(self):
        self.assert_fails(3, trajectory(3, paths=[url("/search", {"q": "Nori"})]))
        wrong_numbers = "Ollie Poodle Mix has fewer days: Ollie has 15 days and Maple has 180 days."
        self.assert_fails(7, trajectory(7, answer=wrong_numbers))

    def test_task_three_rejects_facts_visible_on_search_card_only(self):
        leaked_card_answer = "Nori is a Holland Lop Mix, Adult, in Seattle, WA."
        self.assert_fails(3, trajectory(3, answer=leaked_card_answer))

    def test_login_tasks_require_credential_inputs(self):
        for index in (4, 5, 8, 9, 14):
            observed = trajectory(index)
            observed["steps"] = [
                step for step in observed["steps"]
                if not (step["url"].startswith(url("/login")) and step["action"] == "input")
            ]
            with self.subTest(index=index):
                self.assert_fails(index, observed, mutate=index in {5, 8, 9})

    def test_inquiry_requires_exact_entered_message(self):
        observed = trajectory(9)
        for step in observed["steps"]:
            if step["action"] == "input" and step["url"] == url("/pets/nori-rabbit"):
                step["params"]["text"] = "I would like to meet Nori."
        self.assert_fails(9, observed, mutate=True)

    def test_task_ten_requires_every_matching_detail(self):
        missing_phoebe = [path for path in PATHS[10] if not path.endswith("/pets/phoebe-samoyed")]
        self.assert_fails(10, trajectory(10, paths=missing_phoebe))

    def test_task_ten_accepts_any_detail_order(self):
        alternate = [PATHS[10][0], PATHS[10][3], PATHS[10][1], PATHS[10][2]]
        self.assert_passes(10, trajectory(10, paths=alternate))

    def test_task_eleven_requires_sorted_second_page(self):
        wrong_page = [url("/pets", {"species": "Dog", "sort": "name", "page": "1"}), url("/pets/leo-vizsla-mix")]
        self.assert_fails(11, trajectory(11, paths=wrong_page))

    def test_task_twelve_requires_location_bound_search(self):
        no_location = [url("/search", {"q": "Seattle Humane"}), url("/pets/mochi-siamese-mix")]
        self.assert_fails(12, trajectory(12, paths=no_location))

    def test_task_thirteen_requires_the_guide_detail(self):
        self.assert_fails(13, trajectory(13, paths=[PATHS[13][0]]))

    def test_task_fourteen_requires_the_save_attempt(self):
        observed = trajectory(14)
        observed["steps"] = [
            step for step in observed["steps"]
            if "Save this pet" not in str(step.get("params", {}).get("locator", ""))
        ]
        self.assert_fails(14, observed)

    def test_task_fourteen_rejects_any_database_change(self):
        result, payload = self.verify(
            14,
            trajectory(14),
            extra_sql=(
                "INSERT INTO saved_item(user_id, listing_id) "
                "SELECT u.id,l.id FROM user u,listing l WHERE lower(u.email)=lower(?) AND l.slug=?",
                ("alice.j@test.com", "luna-domestic-shorthair"),
            ),
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(payload["pass"], payload)

    def test_new_verifiers_derive_facts_from_each_initial_snapshot(self):
        result, payload = self.verify(
            10,
            trajectory(
                10,
                answer="Scout Border Collie has the lowest fee at $295; Ace Whippet is $335 and Phoebe Samoyed is $410.",
            ),
            baseline_sql=("UPDATE listing SET adoption_fee=? WHERE slug=?", (295, "scout-border-collie")),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["pass"], payload)

        result, payload = self.verify(
            12,
            trajectory(
                12,
                answer="Mochi Siamese Mix has a $190 adoption fee, a Short coat, and Lynx Point coloring.",
            ),
            baseline_sql=("UPDATE listing SET adoption_fee=? WHERE slug=?", (190, "mochi-siamese-mix")),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["pass"], payload)

        result, payload = self.verify(
            14,
            trajectory(
                14,
                answer="Milo Labrador Mix was already in favorites, so the total remains 3 favorite pets.",
            ),
            baseline_sql=(
                "INSERT INTO saved_item(user_id, listing_id) "
                "SELECT u.id,l.id FROM user u,listing l WHERE lower(u.email)=lower(?) AND l.slug=?",
                ("alice.j@test.com", "luna-domestic-shorthair"),
            ),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["pass"], payload)

    def test_new_read_tasks_reject_partial_answers(self):
        partials = {
            10: "Scout Border Collie has the lowest fee at $300; Ace Whippet is $335.",
            11: "The first pet on page 2 is Leo Vizsla Mix, a Vizsla Mix.",
            12: "The Baby Cat is Mochi Siamese Mix, a Siamese Mix in Seattle, WA.",
            13: "Set up a rabbit-friendly space: Offer unlimited grass hay; Cover cords and unsafe baseboards.",
            14: "Milo Labrador Mix was already in favorites, so the total remains 3 favorite pets.",
        }
        for index, answer in partials.items():
            with self.subTest(index=index):
                self.assert_fails(index, trajectory(index, answer=answer))


if __name__ == "__main__":
    unittest.main()
