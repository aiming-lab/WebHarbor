"""Shared fixtures for the marriott verifier tests.

Snapshots are copies of the real deterministic seed (``instance_seed/marriott.db``,
rebuilt from the tracked source_data/ snapshots by seed_data.py with
PYTHONHASHSEED=0 and a frozen bcrypt digest; see .build-generated-seed) with the
stateful-task mutations applied through sqlite, and trajectories are hand-written
in the agent_demo/agent.py shape. No LLM.

The seed DB is not tracked in git (it is rebuilt at image-build time), so the
fixture fetches it once from the review container (``wh-marriott-review``) and
caches it; ``MARRIOTT_TEST_SEED_DB`` overrides the location. Run from the
agent_demo env so ``simpleArgParser`` (and Pillow) are importable:

    cd agent_demo && uv run python -m pytest ../sites/marriott/verify/tests -q
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
BASE = "http://localhost:40104"
PASSWORD = "TestPass123!"
CONTAINER = "wh-marriott-review"
CACHE = Path(tempfile.gettempdir()) / "marriott_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("MARRIOTT_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    if CACHE.is_file():
        return CACHE
    local = SITE_DIR / "instance_seed" / "marriott.db"
    if local.is_file():
        return local
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp", f"{CONTAINER}:/opt/WebSyn/marriott/"
                       f"instance_seed/marriott.db", str(CACHE)],
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
            "title": "Marriott Bonvoy",
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
        return (self.fill("/sign-in.mi", email, "input[name=email]")
                    .fill("/sign-in.mi", password, "input[name=password]")
                    .step("/sign-in.mi", "click", {"selector": "button[type=submit]"},
                          url_after="/loyalty/myAccount.mi"))

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
    b = RunBuilder(root, f"Marriott--{index}")
    b.step("/", "goto", {})
    b.done("", final_path="/")
    return root


def run_verifier(index: int, run_dir: Path) -> dict:
    """Run verify_<index>.py --run_dir <run_dir> under the current interpreter."""
    verifier = VERIFY_DIR / f"verify_{index}.py"
    r = subprocess.run([sys.executable, str(verifier), "--run_dir", str(run_dir)],
                       capture_output=True, text=True, cwd=str(VERIFY_DIR),
                       env=dict(os.environ))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"task_id": f"Marriott--{index}", "pass": False,
                "reason": f"verifier crashed: {r.stderr.strip()[-300:]}"}


def db_one(db_path: Path, sql: str, params: tuple | list = ()) -> Any:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def hotel_id(db_path: Path, name: str) -> int:
    return db_one(db_path, "SELECT id FROM hotels WHERE name = ?", (name,))


def room_id(db_path: Path, hotel_name: str, room_name: str) -> int:
    return db_one(db_path, "SELECT id FROM room_types WHERE hotel_id = "
                  "(SELECT id FROM hotels WHERE name = ?) AND name = ?", (hotel_name, room_name))
