"""Shared fixtures for the offline Amtrak verifier tests (no Playwright, no docker, no LLM).

Builds agent_demo/agent.py-shaped run directories from hand-written step lists and
initial/after SQLite snapshots derived from the real seed (``instance_seed/amtrak.db``,
generated on the fly by importing the site if the asset bundle is not present).
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image

TESTS_DIR = Path(__file__).resolve().parent
VERIFY_DIR = TESTS_DIR.parent
SITE_DIR = VERIFY_DIR.parent
SEED_DB = SITE_DIR / "instance_seed" / "amtrak.db"
BASE = "http://localhost:41024"
PASSWORD = "TestPass123!"
ALICE = "alice.j@test.com"


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (240, 244, 248)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png(320, 200)   # a plausible screenshot, above verify_lib.MIN_SCREENSHOT_PX
TINY_PNG = _png(1, 1)  # the forged-thumbnail case the size floor exists to reject

if not SEED_DB.exists():
    # Importing the app materialises instance/ and copies it to instance_seed/ (seed_data.copy_instance_to_seed).
    subprocess.run([sys.executable, "-c", "import app"], cwd=SITE_DIR, check=True)


def step(path: str, action: str = "click", text: str | None = None) -> dict[str, Any]:
    """One trajectory step in the agent.py shape; ``path`` is relative to BASE."""
    params: dict[str, Any] = {"text": text} if text is not None else {}
    url = path if path.startswith("http") else f"{BASE}{path}"
    return {"url": url, "action": action, "params": params}


def login_steps(email: str = ALICE) -> list[dict[str, Any]]:
    return [step("/login", "input", email), step("/login", "input", PASSWORD), step("/login", "click")]


def write_run(run_dir: Path, task_id: str, steps: list[dict[str, Any]], answer: str, png: bytes = PNG) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = run_dir / "screenshots"
    shots.mkdir(exist_ok=True)
    numbered = []
    for index, item in enumerate(steps):
        before, after = f"step_{index:03d}.png", f"step_{index + 1:03d}.png"
        (shots / before).write_bytes(png)
        (shots / after).write_bytes(png)
        numbered.append({"step": index, "title": "Amtrak Demo Mirror", "thought": "", **item,
                         "screenshot_before": before, "screenshot_after": after})
    trajectory = {
        "task": "synthetic", "task_id": task_id, "start_url": f"{BASE}/", "model": "unit-test", "max_steps": 40,
        "steps": numbered, "terminated": bool(answer), "termination_reason": "agent_done" if answer else "max_steps",
        "final_answer": answer if answer else None, "judge_rubric": "", "verifier_path": "",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")


class Snapshot:
    """A copy of the seed with optional SQL applied (after-state builder)."""

    def __init__(self, sql: list[str] | None = None):
        self.sql = list(sql or [])

    def write(self, path: Path) -> Path:
        shutil.copy2(SEED_DB, path)
        if self.sql:
            connection = sqlite3.connect(path)
            try:
                for statement in self.sql:
                    connection.execute(statement)
                connection.commit()
            finally:
                connection.close()
        return path


def seed_scalar(sql: str) -> Any:
    connection = sqlite3.connect(SEED_DB)
    try:
        return connection.execute(sql).fetchone()[0]
    finally:
        connection.close()


def alice_id() -> int:
    return int(seed_scalar(f"SELECT id FROM users WHERE email='{ALICE}'"))


def preferred_station_sql(code: str) -> list[str]:
    uid = alice_id()
    return [f"UPDATE users SET preferred_station_code='{code}' WHERE id={uid}",
            f"UPDATE reward_accounts SET preferred_station_code='{code}' WHERE user_id={uid}"]


def new_booking_sql(code: str = "ZSLYNG", fare: str = "Business", accommodation: str = "Business Seat",
                    origin: str = "NYP", destination: str = "WAS", departure: str = "2026-04-20",
                    train_number: str = "2151", credit_points: bool = True) -> list[str]:
    """Rows the mock checkout writes for a direct NYP->WAS Business booking on 2026-04-20."""
    uid = alice_id()
    trip_id = int(seed_scalar(f"SELECT t.id FROM trips t JOIN trains tr ON tr.id=t.train_id WHERE tr.number='{train_number}' AND t.service_date='{departure}'"))
    fare_id = int(seed_scalar(f"SELECT id FROM fare_classes WHERE name='{fare}'"))
    reward_id = int(seed_scalar(f"SELECT id FROM reward_accounts WHERE user_id={uid}"))
    balance = int(seed_scalar(f"SELECT points_balance FROM reward_accounts WHERE id={reward_id}"))
    points, total = 140, 102.24
    sql = [
        f"INSERT INTO bookings(id,user_id,booking_code,trip_type,status,total_amount,reward_points_earned,contact_email,contact_phone,origin_code,destination_code,departure_date,return_date,notes,created_at) "
        f"VALUES (61,{uid},'{code}','one-way','Confirmed',{total},{points},'{ALICE}','212-555-0101','{origin}','{destination}','{departure}',NULL,'','2026-04-18 17:00:00')",
        f"INSERT INTO passengers(id,user_id,booking_id,first_name,last_name,passenger_type,age_band,accessibility_need,seat_preference,rewards_number,email,phone,is_saved_profile) "
        f"VALUES (81,{uid},61,'Alice','Jordan','Adult','18+','','Window','AGR-47000','{ALICE}','212-555-0101',0)",
        f"INSERT INTO booking_segments(id,booking_id,trip_id,leg_order,route_name,train_number,origin_code,destination_code,depart_dt,arrive_dt,fare_class_name,accommodation_type) "
        f"VALUES (65,61,{trip_id},0,'Acela Express','{train_number}','{origin}','{destination}','{departure} 10:59:00','{departure} 13:49:00','{fare}','{accommodation}')",
        f"INSERT INTO tickets(id,booking_id,passenger_id,trip_id,fare_class_id,accommodation_type,seat_or_room,qr_token,status) "
        f"VALUES (81,61,81,{trip_id},{fare_id},'{accommodation}','Business 5A','{code}-1-1','Issued')",
        f"INSERT INTO payment_mocks(id,booking_id,payment_label,amount,status,approval_code,charged_at) "
        f"VALUES (61,61,'Demo Visa ending in 4242',{total},'Approved','ABCD1234','2026-04-18 20:00:00')",
        f"INSERT INTO reward_activities(id,reward_account_id,posted_at,description,points_delta,balance_after,booking_code,category) "
        f"VALUES (61,{reward_id},'2026-04-18 15:00:00','Booking {code} - Acela Express',{points},{balance + points},'{code}','Travel')",
    ]
    if credit_points:
        sql.append(f"UPDATE reward_accounts SET points_balance=points_balance+{points}, points_ytd=points_ytd+{points}, status_credits=status_credits+1 WHERE id={reward_id}")
    return sql


class VerifierTestCase(unittest.TestCase):
    """Base class: ``self.N`` selects verify_N.py."""

    N = -1

    @property
    def task_id(self) -> str:
        return f"Amtrak--{self.N}"

    def verdict(self, steps: list[dict[str, Any]], answer: str, initial: Snapshot | None = None, after: Snapshot | None = None,
                task_id: str | None = None, snapshots_in_run_dir: bool = False,
                trajectory_updates: dict[str, Any] | None = None, corrupt_screenshot: bool = False,
                tiny_screenshots: bool = False) -> dict[str, Any]:
        initial = initial or Snapshot()
        after = after or Snapshot()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            write_run(run_dir, task_id or self.task_id, steps, answer,
                      png=TINY_PNG if tiny_screenshots else PNG)
            if trajectory_updates:
                path = run_dir / "trajectory.json"
                trajectory = json.loads(path.read_text())
                trajectory.update(trajectory_updates)
                path.write_text(json.dumps(trajectory, indent=2))
            if corrupt_screenshot:
                next((run_dir / "screenshots").glob("*.png")).write_bytes(b"not a png")
            if snapshots_in_run_dir:
                initial.write(run_dir / "initial.db")
                after.write(run_dir / "after.db")
                command = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir), "--no_llm", "True"]
            else:
                command = [sys.executable, str(VERIFY_DIR / f"verify_{self.N}.py"), "--run_dir", str(run_dir),
                           "--initial_db", str(initial.write(root / "initial.db")), "--after_db", str(after.write(root / "after.db"))]
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
