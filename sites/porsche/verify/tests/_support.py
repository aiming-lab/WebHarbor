"""Shared fixtures for the porsche verifier tests.

Snapshots are copies of the real deterministic seed (instance_seed/porsche.db,
built at image time with PYTHONHASHSEED=0) with the stateful-task mutations
applied through sqlite, and trajectories are hand-written in the
agent_demo/agent.py shape. No LLM.

The seed DB resolves from the review container (wh-porsche-review); the
PORSCHE_TEST_SEED_DB env var overrides the location. Run with plain
python3 + pytest:

    python3 -m pytest sites/porsche/verify/tests -q
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
BASE = "http://localhost:40120"
PASSWORD = "TestPass123!"
CONTAINER = "wh-porsche-review"
CACHE = Path(tempfile.gettempdir()) / "porsche_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("PORSCHE_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp", f"{CONTAINER}:/opt/WebSyn/porsche/"
                       f"instance_seed/porsche.db", str(CACHE)],
                       capture_output=True, text=True)
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
        return (len(data).to_bytes(4, "big") + tag + data
                + zlib.crc32(tag + data).to_bytes(4, "big"))

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = tiny_png()


# ------------------------------------------------------------------ run-dir builder
class RunBuilder:
    """Hand-writes an agent_demo-shaped run directory: trajectory.json + screenshots/."""

    def __init__(self, root: Path, task_id: str, start_path: str = "/"):
        self.root = root
        self.shots_dir = root / "screenshots"
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        (self.shots_dir / "step_000.png").write_bytes(PNG)
        self.steps: list[dict[str, Any]] = []
        self.task_id = task_id
        self.start_url = BASE + start_path
        self.final_answer: str | None = None
        self.final_path = start_path

    def step(self, path: str, action: str = "click", params: dict | None = None,
             url_after: str | None = None, url: str | None = None):
        i = len(self.steps)
        before = f"step_{i:03d}.png"
        after = f"step_{i + 1:03d}.png"
        (self.shots_dir / after).write_bytes(PNG)
        self.steps.append({
            "step": i,
            "url": (url if url is not None else (BASE + path if path.startswith("/") else path)),
            "title": "Porsche",
            "thought": f"review fixture step on {path}",
            "action": action,
            "params": params or {},
            "observed_text": "fixture",
            "observed_text_before": "fixture",
            "screenshot_before": before,
            "screenshot_after": after,
            **({"url_after": (BASE + url_after if url_after and url_after.startswith("/")
                              else url_after)} if url_after else {}),
        })
        self.final_path = url_after or path

    def done(self, answer: str):
        self.final_answer = answer
        (self.root / "trajectory.json").write_text(json.dumps({
            "task_id": self.task_id,
            "start_url": self.start_url,
            "final_url": BASE + self.final_path,
            "terminated": True,
            "termination_reason": "agent_done",
            "steps": self.steps,
            "final_answer": answer,
        }, indent=1), encoding="utf-8")
        return self.root


def build_run(tmp: Path, task_id: str, steps_builder, answer: str,
              start_path: str = "/") -> Path:
    run = RunBuilder(tmp, task_id, start_path)
    steps_builder(run)
    return run.done(answer)


def noop_run(tmp: Path, task_id: str) -> Path:
    """Homepage-only, empty answer, clean DB: every verifier must FAIL this."""
    run = RunBuilder(tmp, task_id)
    run.step("/", action="goto")
    return run.done("")


def run_verifier(task_index: int, run_dir: Path, initial_db: Path, after_db: Path):
    """Run verify_<n>.py as a subprocess; returns (exit_code, parsed_json)."""
    script = VERIFY_DIR / f"verify_{task_index}.py"
    proc = subprocess.run([sys.executable, str(script),
                            "--run_dir", str(run_dir),
                            "--initial_db", str(initial_db),
                            "--after_db", str(after_db)],
                           capture_output=True, text=True, cwd=str(VERIFY_DIR))
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        payload = {"parse_error": proc.stdout[-400:], "stderr": proc.stderr[-400:]}
    return proc.returncode, payload


def db_one(db_path: Path, query: str, args: tuple = ()) -> Any:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return con.execute(query, args).fetchone()
    finally:
        con.close()


def mutate_db(db_path: Path, statements: list[str]) -> None:
    con = sqlite3.connect(db_path)
    try:
        for stmt in statements:
            con.execute(stmt)
        con.commit()
    finally:
        con.close()
