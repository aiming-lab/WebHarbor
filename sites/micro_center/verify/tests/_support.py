"""Shared fixtures for the micro_center verifier tests.

Snapshots are copies of the real frozen seed (instance_seed/micro_center.db,
shipped in the pinned asset archive) with the stateful-task mutations applied
through sqlite, and trajectories are hand-written in the agent_demo/agent.py
shape. No LLM.

The seed DB resolves from the review container (wh-mc-review); the
MC_TEST_SEED_DB env var overrides the location. Run with plain python3 + pytest:

    python3 -m pytest sites/micro_center/verify/tests -q
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
sys.path.insert(0, str(VERIFY_DIR))

BASE = "http://localhost:40089"
PASSWORD = "TestPass123!"
CONTAINER = "wh-mc-review"
CACHE = Path(tempfile.gettempdir()) / "mc_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("MC_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp", f"{CONTAINER}:/opt/WebSyn/micro_center/"
                       f"instance_seed/micro_center.db", str(CACHE)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot acquire the seed DB (docker cp failed): {r.stderr[:200]}")
    return CACHE


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
            "title": "Micro Center",
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
        self.final_path = path
        return self

    def fill(self, path: str, text: str, selector: str = "input"):
        return self.step(path, "fill", {"text": text, "selector": selector})

    def login(self, email: str, password: str = PASSWORD):
        return (self.fill("/account/signin", email, ".form-card input[name='email']")
                    .fill("/account/signin", password, ".form-card input[name='password']")
                    .step("/account/signin", "click",
                          {"selector": ".form-card button[type='submit']"},
                          url_after="/account"))

    def search(self, query: str):
        return self.step(f"/search/search_results.aspx?Ntt={query.replace(' ', '+')}",
                         "goto", {})

    def product(self, pid: int, slug: str = "fixture-product"):
        return self.step(f"/product/{pid:07d}/{slug}", "goto", {})

    def done(self, answer: str, final_path: str | None = None, terminated: bool = True,
             reason: str = "agent_done", task_id: str | None = None):
        self.final_answer = answer
        traj = {
            "task": f"{task_id or self.task_id} fixture",
            "task_id": task_id or self.task_id,
            "start_url": self.start_url,
            "model": "fixture",
            "max_steps": 120,
            "steps": self.steps,
            "terminated": terminated,
            "termination_reason": reason,
            "final_answer": answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (final_path or self.final_path),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return traj

    # tampering helpers
    def tamper_task_id(self, wrong: str):
        traj = json.loads((self.root / "trajectory.json").read_text())
        traj["task_id"] = wrong
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))

    def tamper_offsite_url(self):
        traj = json.loads((self.root / "trajectory.json").read_text())
        traj["steps"][0]["url"] = "https://example.com/phish"
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))

    def tamper_missing_screenshot(self):
        shot = self.shots_dir / "step_001.png"
        if shot.is_file():
            shot.unlink()
        else:
            (self.shots_dir / "step_001.png")  # no-op touch of name
            traj = json.loads((self.root / "trajectory.json").read_text())
            traj["steps"][0]["screenshot_after"] = "step_missing.png"
            (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))

    def tamper_not_done(self):
        traj = json.loads((self.root / "trajectory.json").read_text())
        traj["terminated"] = False
        traj["termination_reason"] = "max_steps"
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))


def build_run(tmp: Path, name: str, task_id: str, start: str = "/") -> RunBuilder:
    root = tmp / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return RunBuilder(root, task_id, start)


def noop_run(tmp: Path, name: str, task_id: str) -> Path:
    """Homepage-only run with an empty answer and a clean DB."""
    b = build_run(tmp, name, task_id)
    b.step("/", "goto", {})
    b.done("")
    return b.root


def copy_db(source: Path, dest: Path) -> Path:
    shutil.copy2(source, dest)
    return dest


def mutate_db(source: Path, dest: Path, statements: list[tuple[str, tuple | list]]) -> Path:
    shutil.copy2(source, dest)
    con = sqlite3.connect(str(dest))
    try:
        for sql, params in statements:
            con.execute(sql, tuple(params))
        con.commit()
    finally:
        con.close()
    return dest


def db_one(db_path: Path | str, sql: str, params: tuple | list = ()):  # type: ignore[name-defined]
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(sql, tuple(params)).fetchone()
        return row
    finally:
        con.close()


def run_verifier(task_id: str, run_dir: Path, initial_db: Path, after_db: Path):
    idx = int(task_id.split("--")[1])
    script = VERIFY_DIR / f"verify_{idx}.py"
    r = subprocess.run([sys.executable, str(script), "--run_dir", str(run_dir),
                        "--initial_db", str(initial_db), "--after_db", str(after_db),
                        "--no_llm", "True"],
                       capture_output=True, text=True, timeout=180)
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {"task_id": task_id, "pass": False,
                   "reason": f"verifier crashed: {r.stderr[-300:] or r.stdout[-300:]}"}
    return r.returncode, payload
