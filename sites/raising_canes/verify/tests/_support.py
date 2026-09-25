"""Shared fixtures for the raising_canes verifier tests.

Snapshots are copies of the real deterministic seed (instance_seed/
raising_canes.db, built at image time with PYTHONHASHSEED=0) with the
stateful-task mutations applied through sqlite, and trajectories are
hand-written in the agent_demo/agent.py shape. No LLM.

The seed DB resolves from the review container (wh-rc-review); the
RC_TEST_SEED_DB env var overrides the location. Run with plain python3 +
pytest:

    python3 -m pytest sites/raising_canes/verify/tests -q
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
BASE = "http://localhost:40127"
PASSWORD = "TestPass123!"
CONTAINER = "wh-rc-review"
CACHE = Path(tempfile.gettempdir()) / "rc_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("RC_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp",
                        f"{CONTAINER}:/opt/WebSyn/raising_canes/instance_seed/raising_canes.db",
                        str(CACHE)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot acquire the seed DB (docker cp failed): {r.stderr[:200]}")
    return CACHE


# ------------------------------------------------------------------ tiny valid PNG
def tiny_png(width: int = 4, height: int = 4) -> bytes:
    raw = b"".join(b"\x00" + b"\x40\x90\xd0" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (len(data).to_bytes(4, "big") + tag + data
                + zlib.crc32(tag + data).to_bytes(4, "big"))

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + zlib.compress(raw) + chunk(b"IEND", b""))


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
            "title": "Raising Cane's",
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
        return (self.fill("/login", email, "input[name=email]")
                    .fill("/login", password, "input[name=password]")
                    .step("/login", "click", {"selector": "button[type=submit]"},
                          url_after="/account"))

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

    def goto(self, path: str):
        return self.step(path, "goto", {})


def build_run(tmp: Path, name: str, task_id: str, start: str = "/") -> RunBuilder:
    root = tmp / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return RunBuilder(root, task_id, start)


def copy_db(source: Path, dest: Path) -> Path:
    shutil.copy2(source, dest)
    return dest


def mutate_db(source: Path, dest: Path, statements: list[tuple[str, tuple | list]]) -> Path:
    """Copy the seed and apply (sql, params) statements."""
    shutil.copy2(source, dest)
    con = sqlite3.connect(str(dest))
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return dest


def noop_run(tmp: Path, index: int) -> Path:
    """Homepage-only, empty-answer, clean-DB run dir (initial == after == seed)."""
    root = tmp / f"noop_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    seed = _acquire_seed()
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Raising Cane's--{index}")
    b.step("/", "goto", {})
    b.done("", final_path="/")
    return root


def run_verifier(index: int, run_dir: Path) -> dict:
    """Run verify_<index>.py --run_dir <run_dir> under the current interpreter."""
    if not (run_dir / "initial.db").is_file():
        copy_db(_acquire_seed(), run_dir / "initial.db")
    verifier = VERIFY_DIR / f"verify_{index}.py"
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    r = subprocess.run([sys.executable, str(verifier), "--run_dir", str(run_dir)],
                       capture_output=True, text=True, cwd=str(VERIFY_DIR), env=env)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"task_id": f"Raising Cane's--{index}", "pass": False,
                "reason": "verifier_crashed", "stdout": r.stdout[-400:],
                "stderr": r.stderr[-400:]}


def db_one(db_path: Path | str, sql: str, params: tuple = ()) -> Any:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()
