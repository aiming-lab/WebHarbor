"""Shared fixtures for the webmd_doctor verifier tests.

Synthetic snapshots are copies of the frozen seed (``instance_seed/webmd_doctor.db``)
with the four runtime tables rewritten from a small in-memory ``State``; hand-written
trajectories follow the agent_demo/agent.py shape. No docker, no LLM.
"""
from __future__ import annotations

import base64
import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
SEED_DB = SITE_DIR / "instance_seed" / "webmd_doctor.db"
BASE = "http://localhost:41024"
PASSWORD = "TestPass123!"
STAMP = "2026-08-01 00:00:00.000000"
FIXTURE_HASH = "scrypt:32768:8:1$fixture$invalid"

if not SEED_DB.exists():  # pragma: no cover - environment guard
    raise unittest.SkipTest(f"frozen seed missing: {SEED_DB} (run ./scripts/fetch_assets.sh webmd_doctor)")

# Same ids / e-mails / relations as the frozen seed (all synthetic).
SEED_USERS = [
    dict(id=1, email="alice.j@test.com", display_name="Alice Johnson", dob="1988-04-12"),
    dict(id=2, email="bob.c@test.com", display_name="Bob Chen", dob="1979-11-03"),
    dict(id=3, email="carol.d@test.com", display_name="Carol Davis", dob="1993-07-21"),
    dict(id=4, email="david.k@test.com", display_name="David Kim", dob="1984-02-09"),
]
SEED_SAVED = [(1, 1, 5), (2, 1, 47), (3, 1, 64), (4, 2, 23)]
SEED_APPOINTMENTS = [
    dict(id=1, user_id=1, doctor_id=106, location_id=166, patient_type="Returning Patient",
         slot_date="2026-09-11", slot_time="9:30 AM", reference="WMD-JASDV25V"),
]
SEED_REVIEWS = [
    dict(id=1, user_id=1, doctor_id=47, rating=4, c1=1, c2=1, c3=0, c4=1, c5=1, c6=1, c7=0,
         text="Thorough annual visit and clear answers about my lab results; scheduling the follow-up took two calls.",
         status="Pending review"),
]


class State:
    """Mutable copy of the seeded users / saved_providers / appointment_requests / user_reviews."""

    def __init__(self) -> None:
        self.users = copy.deepcopy(SEED_USERS)
        self.saved = list(SEED_SAVED)
        self.appointments = copy.deepcopy(SEED_APPOINTMENTS)
        self.reviews = copy.deepcopy(SEED_REVIEWS)
        self.extra_sql: list[str] = []

    # -- mutators -----------------------------------------------------------
    def add_user(self, email: str) -> int:
        new_id = max(user["id"] for user in self.users) + 1
        self.users.append(dict(id=new_id, email=email, display_name=email.split("@")[0], dob=None))
        return new_id

    def add_saved(self, user_id: int, doctor_id: int) -> int:
        new_id = max([row[0] for row in self.saved] + [0]) + 1
        self.saved.append((new_id, user_id, doctor_id))
        return new_id

    def remove_saved(self, user_id: int, doctor_id: int) -> None:
        before = len(self.saved)
        self.saved = [row for row in self.saved if not (row[1] == user_id and row[2] == doctor_id)]
        assert len(self.saved) == before - 1, f"no saved row {user_id}/{doctor_id}"

    def add_appointment(self, user_id: int, doctor_id: int, location_id: int, patient_type: str = "New Patient",
                        slot_date: str = "2026-09-14", slot_time: str = "10:30 AM", reference: str = "WMD-AB2CD3EF") -> str:
        new_id = max(row["id"] for row in self.appointments) + 1
        self.appointments.append(dict(id=new_id, user_id=user_id, doctor_id=doctor_id, location_id=location_id,
                                      patient_type=patient_type, slot_date=slot_date, slot_time=slot_time, reference=reference))
        return reference

    def add_review(self, user_id: int, doctor_id: int, rating: int, text: str, status: str = "Pending review") -> int:
        new_id = max(row["id"] for row in self.reviews) + 1
        self.reviews.append(dict(id=new_id, user_id=user_id, doctor_id=doctor_id, rating=rating, c1=1, c2=1, c3=1,
                                 c4=1, c5=1, c6=1, c7=1, text=text, status=status))
        return new_id

    # -- persistence --------------------------------------------------------
    def write(self, path: Path) -> Path:
        shutil.copy2(SEED_DB, path)
        connection = sqlite3.connect(path)
        try:
            for table in ("saved_providers", "appointment_requests", "user_reviews", "users"):
                connection.execute(f"DELETE FROM {table}")
            connection.executemany(
                "INSERT INTO users(id, email, password_hash, dob, display_name, created_at) VALUES (:id, :email, :hash, :dob, :display_name, :stamp)",
                [{**user, "hash": FIXTURE_HASH, "stamp": STAMP} for user in self.users],
            )
            connection.executemany(
                f"INSERT INTO saved_providers(id, user_id, doctor_id, saved_at) VALUES (?, ?, ?, '{STAMP}')",
                self.saved,
            )
            connection.executemany(
                "INSERT INTO appointment_requests(id, user_id, doctor_id, location_id, patient_type, slot_date, slot_time, reference, created_at) "
                f"VALUES (:id, :user_id, :doctor_id, :location_id, :patient_type, :slot_date, :slot_time, :reference, '{STAMP}')",
                self.appointments,
            )
            connection.executemany(
                "INSERT INTO user_reviews(id, user_id, doctor_id, rating, c1, c2, c3, c4, c5, c6, c7, text, status, created_at) "
                f"VALUES (:id, :user_id, :doctor_id, :rating, :c1, :c2, :c3, :c4, :c5, :c6, :c7, :text, :status, '{STAMP}')",
                self.reviews,
            )
            for statement in self.extra_sql:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()
        return path


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    """One trajectory step in the agent.py shape; ``path`` is relative to BASE."""
    params: dict[str, Any] = {"text": text} if text is not None else {}
    url = path if path.startswith("http") else f"{BASE}{path}"
    return {"url": url, "action": action, "params": params}


def profile(slug: str) -> str:
    return f"/doctor/{slug}-overview"


def login_steps(email: str) -> list[dict[str, Any]]:
    return [step("/login", "input", email), step("/login", "input", PASSWORD), step("/login", "click")]


def signup_steps(email: str) -> list[dict[str, Any]]:
    return [step("/login"), step("/signup", "input", email), step("/signup", "input", "DrivePass9!"), step("/signup", "click")]


def only_paths(steps: list[dict[str, Any]], *allowed: str) -> list[dict[str, Any]]:
    """Keep the steps whose URL path is one of ``allowed`` (shortcut trajectories)."""
    from urllib.parse import urlparse

    def path_of(item: dict[str, Any]) -> str:
        return urlparse(item["url"]).path.rstrip("/") or "/"

    return [item for item in steps if path_of(item) in allowed]


def write_run(run_dir: Path, task_id: str, steps: list[dict[str, Any]], answer: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = run_dir / "screenshots"
    shots.mkdir(exist_ok=True)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    numbered = []
    for index, item in enumerate(steps):
        before = f"step_{index:03d}.png"
        after = f"step_{index + 1:03d}.png"
        (shots / before).write_bytes(png)
        (shots / after).write_bytes(png)
        numbered.append({"step": index, **item, "screenshot_before": before, "screenshot_after": after})
    trajectory = {
        "task": "synthetic", "task_id": task_id, "start_url": f"{BASE}/", "model": "unit-test",
        "max_steps": 30, "steps": numbered, "terminated": bool(answer),
        "termination_reason": "agent_done" if answer else "max_steps",
        "final_answer": answer if answer else None,
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")


class VerifierTestCase(unittest.TestCase):
    """Base class: ``self.N`` selects verify_N.py; subclasses define GENUINE_STEPS / ANSWER / genuine_after."""

    N = -1
    GENUINE_STEPS: list[dict[str, Any]] = []
    ANSWER = ""

    @property
    def task_id(self) -> str:
        return f"WebMD Doctor--{self.N}"

    def genuine_after(self) -> State:
        return State()

    def verdict(
        self,
        steps: list[dict[str, Any]],
        answer: str,
        initial: State | None = None,
        after: State | None = None,
        task_id: str | None = None,
        snapshots_in_run_dir: bool = False,
        trajectory_updates: dict[str, Any] | None = None,
        corrupt_screenshot: bool = False,
    ) -> dict[str, Any]:
        initial = initial or State()
        after = after or State()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            write_run(run_dir, task_id or self.task_id, steps, answer)
            if trajectory_updates:
                trajectory_path = run_dir / "trajectory.json"
                trajectory = json.loads(trajectory_path.read_text())
                trajectory.update(trajectory_updates)
                trajectory_path.write_text(json.dumps(trajectory, indent=2))
            if corrupt_screenshot:
                first = next((run_dir / "screenshots").glob("*.png"))
                first.write_bytes(b"not a png")
            if snapshots_in_run_dir:
                initial.write(run_dir / "initial.db")
                after.write(run_dir / "after.db")
                command = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir)]
            else:
                command = [
                    sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir),
                    "--initial_db", str(initial.write(root / "initial.db")),
                    "--after_db", str(after.write(root / "after.db")),
                ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertTrue(result.stdout.strip(), f"verifier printed nothing; stderr={result.stderr}")
            verdict = json.loads(result.stdout)
            verdict["returncode"] = result.returncode
            return verdict

    def assertPasses(self, verdict: dict[str, Any]) -> None:
        self.assertTrue(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 0)
        self.assertEqual(verdict["reason"], "all checks passed")

    def assertFailsOn(self, verdict: dict[str, Any], reason: str) -> None:
        self.assertFalse(verdict["pass"], verdict["evidence"])
        self.assertEqual(verdict["returncode"], 1)
        self.assertEqual(verdict["reason"], reason, verdict["evidence"])


class SharedVerifierTests:
    """Mixin (not a TestCase, so it is never collected on its own): negatives every verifier rejects."""

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), snapshots_in_run_dir=True))

    def test_noop_run_fails_on_empty_answer(self) -> None:
        self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_other_task_trajectory_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), task_id="WebMD Doctor--99")
        self.assertFailsOn(verdict, "trajectory_task_matches")

    def test_unterminated_run_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), trajectory_updates={"terminated": False})
        self.assertFailsOn(verdict, "trajectory_completed")

    def test_mixed_origin_run_fails(self) -> None:
        verdict = self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(),
                               trajectory_updates={"start_url": "http://127.0.0.1:41024/"})
        self.assertFailsOn(verdict, "all_urls_match_local_origin")

    def test_corrupt_screenshot_fails(self) -> None:
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=self.genuine_after(), corrupt_screenshot=True), "screenshots_decode")

    def test_schema_change_fails_closed(self) -> None:
        after = self.genuine_after()
        after.extra_sql.append("CREATE TABLE injected(id INTEGER PRIMARY KEY)")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "snapshot_contract_invalid")

    def test_catalog_change_fails_closed(self) -> None:
        after = self.genuine_after()
        after.extra_sql.append("UPDATE doctors SET medical_school='tampered' WHERE id=1")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "snapshot_contract_invalid")

    def test_wrong_seed_marker_fails_closed(self) -> None:
        initial = State()
        initial.extra_sql.append("UPDATE seed_metadata SET value='wrong' WHERE key='version'")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, initial=initial, after=self.genuine_after()), "snapshot_contract_invalid")

    def test_retargeted_seed_fails_closed(self) -> None:
        # ground_truth.py re-derives the target from the initial snapshot: a seed whose
        # specialties no longer select the target must fail closed, never grade against stale constants.
        initial = State()
        initial.extra_sql.append("UPDATE doctors SET primary_specialty_id = 10, secondary_specialty_id = NULL")
        after = self.genuine_after()
        after.extra_sql.append("UPDATE doctors SET primary_specialty_id = 10, secondary_specialty_id = NULL")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, initial=initial, after=after), "snapshot_contract_invalid")
