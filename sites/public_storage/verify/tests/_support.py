"""Shared fixtures for the public_storage verifier tests.

Snapshots are copies of the real deterministic seed
(instance_seed/public_storage.db, built at image time with PYTHONHASHSEED=0)
with the stateful-task mutations applied through sqlite, and trajectories are
hand-written in the agent_demo/agent.py shape. No LLM.

The seed DB resolves from the review container (wh-public-storage-review);
the PUBLIC_STORAGE_TEST_SEED_DB env var overrides the location. Run with
plain python3 + pytest:

    python3 -m pytest sites/public_storage/verify/tests -q
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
BASE = "http://127.0.0.1:47088"
PASSWORD = "TestPass123!"
CONTAINER = "wh-public-storage-review"
CACHE = Path(tempfile.gettempdir()) / "public_storage_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("PUBLIC_STORAGE_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp",
                        f"{CONTAINER}:/opt/WebSyn/public_storage/instance_seed/public_storage.db",
                        str(CACHE)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot acquire the seed DB (docker cp failed): {r.stderr[:200]}")
    return CACHE


def copy_db(target: Path) -> Path:
    """Copy the frozen seed to the requested path."""
    shutil.copyfile(_acquire_seed(), target)
    return target


# ------------------------------------------------------------------ tiny valid PNG
def tiny_png(width: int = 4, height: int = 4) -> bytes:
    """Minimal valid single-color PNG (no Pillow needed at fixture-build time)."""
    raw = b"".join(b"\x00" + b"\x40\x90\xd0" * width for _ in range(height))
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


# ------------------------------------------------------------------ run building
class RunBuilder:
    """Trajectory in the agent_demo/agent.py shape."""

    def __init__(self, task_id: str, start_url: str = BASE + "/"):
        self.traj: dict[str, Any] = {
            "task_id": task_id,
            "start_url": start_url,
            "final_url": start_url,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": "",
            "steps": [],
        }

    def goto(self, url: str) -> "RunBuilder":
        self.traj["steps"].append({"action": "goto", "url": url,
                                   "url_before": self.traj["final_url"],
                                   "url_after": url})
        self.traj["final_url"] = url
        return self

    def click(self, url: str) -> "RunBuilder":
        self.traj["steps"].append({"action": "click", "url": url,
                                   "url_before": self.traj["final_url"],
                                   "url_after": url})
        self.traj["final_url"] = url
        return self

    def fill(self, url: str, text: str) -> "RunBuilder":
        self.traj["steps"].append({"action": "fill", "url": url,
                                   "params": {"text": text},
                                   "url_before": self.traj["final_url"],
                                   "url_after": url})
        self.traj["final_url"] = url
        return self

    def answer(self, text: str) -> "RunBuilder":
        self.traj["final_answer"] = text
        return self

    def done(self) -> "RunBuilder":
        self.traj["terminated"] = True
        self.traj["termination_reason"] = "agent_done"
        return self


def build_run(tmp: Path, name: str, traj: RunBuilder) -> Path:
    d = tmp / name
    d.mkdir(parents=True)
    shots = d / "screenshots"
    shots.mkdir()
    (shots / "step_000.png").write_bytes(tiny_png())
    (shots / "step_001.png").write_bytes(tiny_png())
    (d / "trajectory.json").write_text(json.dumps(traj.traj))
    return d


def noop_run(tmp: Path, task_id: str) -> Path:
    b = RunBuilder(task_id)
    b.goto(BASE + "/")
    b.answer("")
    return build_run(tmp, "noop", b)


def run_verifier(n: int, run_dir: Path, initial_db: Path | None = None,
                 after_db: Path | None = None, container: str | None = None) -> dict:
    env = dict(os.environ)
    if container:
        env["WH_CONTAINER"] = container
    cmd = [sys.executable, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir)]
    if initial_db is not None:
        cmd += ["--initial_db", str(initial_db)]
    if after_db is not None:
        cmd += ["--after_db", str(after_db)]
    if container:
        cmd += ["--container", container]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"task_id": f"Public Storage--{n}", "pass": False,
                "reason": f"bad verifier output: {r.stdout[:200]} {r.stderr[:200]}"}


# ------------------------------------------------------------------ db helpers
def db_one(db: Path, sql: str, args: tuple = ()) -> Any:
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, args).fetchone()
    finally:
        con.close()


def db_exec(db: Path, sql: str, args: tuple = ()) -> None:
    con = sqlite3.connect(db)
    try:
        con.execute(sql, args)
        con.commit()
    finally:
        con.close()


def mutate_db(src: Path, dst: Path, statements: list[tuple[str, tuple]]) -> Path:
    """Copy the seed then apply (sql, args) mutations."""
    shutil.copyfile(src, dst)
    con = sqlite3.connect(dst)
    try:
        for sql, args in statements:
            con.execute(sql, args)
        con.commit()
    finally:
        con.close()
    return dst


def add_reservation(db: Path, code: str, unit_id: str, facility_id: int,
                    name: str, email: str, phone: str, move_in: str,
                    status: str = "held", user_id: int | None = None) -> int:
    unit_row = db_one(db, "SELECT id FROM units WHERE unit_id = ?", (unit_id,))[0]
    con = sqlite3.connect(db)
    try:
        cur = con.execute(
            "INSERT INTO reservations (code, user_id, facility_id, unit_row_id,"
            " holder_name, holder_email, holder_phone, move_in_date, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, user_id, facility_id, unit_row, name, email, phone, move_in,
             status, "09/24/2026"))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def add_user(db: Path, email: str, first: str, last: str, phone: str,
             password_hash: str = "x" * 60, account_number: str = "888777") -> int:
    con = sqlite3.connect(db)
    try:
        cur = con.execute(
            "INSERT INTO users (username, email, password_hash, first_name,"
            " last_name, phone, account_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email.split("@")[0] + "999", email, password_hash, first, last,
             phone, account_number))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def add_payment(db: Path, rental_id: int, confirmation: str, amount: float,
                last4: str = "4242") -> int:
    con = sqlite3.connect(db)
    try:
        cur = con.execute(
            "INSERT INTO payments (rental_id, confirmation, amount, card_last4, paid_on)"
            " VALUES (?, ?, ?, ?, ?)",
            (rental_id, confirmation, amount, last4, "09/24/2026"))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()
