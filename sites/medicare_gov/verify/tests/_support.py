"""Shared fixtures for the medicare_gov verifier tests (15 redesigned tasks).

Snapshots are copies of the real deterministic seed (``instance_seed/medicare_gov.db``,
rebuilt from the tracked source_data.json by ``seed_data.py`` with PYTHONHASHSEED=0;
see ``.build-generated-seed``) with mutations applied through sqlite, and
trajectories are hand-written in the ``agent_demo/agent.py`` shape (step ``url``
= page before the action). No docker, no LLM.

Run from the agent_demo env so ``simpleArgParser`` (and Pillow) are importable:

    cd agent_demo && uv run python -m pytest ../sites/medicare_gov/verify/tests -q
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
SEED_DB = Path(os.environ.get("MG_TEST_SEED_DB")
               or SITE_DIR / "instance_seed" / "medicare_gov.db")
BASE = "http://localhost:40078"
PASSWORD = "TestPass123!"
EMAILS = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
          "carol": "carol.d@test.com", "david": "david.k@test.com"}
USER_ID = {"alice.j@test.com": 1, "bob.c@test.com": 2,
           "carol.d@test.com": 3, "david.k@test.com": 4}

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
             url_after: str | None = None, page_text: str = "fixture page"):
        i = len(self.steps)
        before = f"step_{i:03d}.png"
        after = f"step_{i + 1:03d}.png"
        (self.shots_dir / after).write_bytes(PNG)
        url = BASE + path if path.startswith("/") else path
        self.steps.append({
            "step": i,
            "url": url,
            "title": "Medicare",
            "page_text": page_text,
            "thought": f"review fixture step on {path}",
            "action": action,
            "params": params or {},
            "observed_text": page_text,
            "observed_text_before": page_text,
            "screenshot_before": before,
            "screenshot_after": after,
            **({"url_after": (BASE + url_after if url_after and url_after.startswith("/")
                             else url_after)} if url_after else {}),
        })
        self.final_path = path
        return self

    def fill(self, path: str, text: str, selector: str = "input"):
        return self.step(path, "fill", {"text": text, "selector": selector})

    def login(self, email: str):
        return (self.fill("/account/login", email, "input[name=email]")
                    .fill("/account/login", PASSWORD, "input[name=password]")
                    .step("/account/login", "click", {"selector": "button[type=submit]"},
                          url_after="/my/dashboard"))

    def done(self, answer: str, final_path: str | None = None):
        self.final_answer = answer
        if final_path:
            self.final_path = final_path
        return self

    def write(self, *, terminated: bool = True, reason: str = "agent_done",
              task_id: str | None = None) -> Path:
        traj = {
            "task": f"fixture for {self.task_id}",
            "task_id": task_id or self.task_id,
            "start_url": self.start_url,
            "model": "review-fixture",
            "max_steps": 60,
            "steps": self.steps,
            "terminated": terminated,
            "termination_reason": reason,
            "final_answer": self.final_answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (self.final_path if self.final_path.startswith("/") else "/"),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return self.root


# ------------------------------------------------------------------ DB helpers
def copy_db(dest: Path) -> Path:
    shutil.copyfile(SEED_DB, dest)
    return dest


def mutate_db(db_path: Path, statements) -> Path:
    con = sqlite3.connect(db_path)
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return db_path


def login_statements(user_id: int, email: str = ""):
    """The exact login_events row one honest login writes (hidden device field)."""
    return [("INSERT INTO login_events (user_id, \"when\", method, device) "
             "VALUES (?, '2026-09-23', 'Medicare.gov account', 'Chrome on Windows')",
             (user_id,))]


# ------------------------------------------------------------------ verifier runner
def run_verifier(task_index: int, run_dir: Path, initial_db: Path, after_db: Path,
                 expect_pass: bool):
    """Run verify_<task_index>.py against a run dir + snapshots; return the JSON verdict."""
    script = VERIFY_DIR / f"verify_{task_index}.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial_db), "--after_db", str(after_db), "--no_llm", "True"],
        capture_output=True, text=True, cwd=str(VERIFY_DIR))
    verdict = {}
    try:
        verdict = json.loads(proc.stdout)
    except json.JSONDecodeError:
        verdict = {"pass": False, "parse_error": proc.stdout[-500:], "stderr": proc.stderr[-800:]}
    if expect_pass and verdict.get("pass") is not True:
        raise AssertionError(f"expected PASS for task {task_index}, got: {verdict}")
    if (not expect_pass) and verdict.get("pass") is not False:
        raise AssertionError(f"expected FAIL for task {task_index}, got: {verdict}")
    return verdict


# ------------------------------------------------------------------ canonical fixtures
def noop_run(root: Path, task_id: str) -> Path:
    """Homepage-only, empty answer, clean DB — every verifier must FAIL this."""
    b = RunBuilder(root, task_id)
    b.step("/", "click", {"selector": "body"})
    b.done("")
    return b.write()
