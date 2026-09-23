"""Shared fixtures for the league_of_legends verifier tests.

Snapshots are copies of the real deterministic seed (``instance_seed/league_of_legends.db``,
rebuilt from the tracked source_data.json by ``seed_data.py``; PYTHONHASHSEED-independent,
byte-identical double build covered by the site's own pytest; see .build-generated-seed)
with mutations applied through sqlite, and trajectories are hand-written in the
``agent_demo/agent.py`` shape (step ``url`` = page before the action). No LLM.

The seed DB is not tracked in git (it ships in the pinned asset bundle / is rebuilt at
image-build time), so the fixture fetches it once from the review container
(``wh-rev-league_of_legends``) and caches it; ``LOL_TEST_SEED_DB`` overrides the
location. Run from the agent_demo env so ``simpleArgParser`` (and Pillow) are
importable:

    cd agent_demo && uv run python -m pytest ../sites/league_of_legends/verify/tests -q
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
BASE = "http://localhost:40078"
PASSWORD = "TestPass123!"
CONTAINER = "wh-rev-league_of_legends"
CACHE = Path(tempfile.gettempdir()) / "lol_verify_tests_seed.db"

SEED_DB = Path(os.environ.get("LOL_TEST_SEED_DB") or "")


def _acquire_seed() -> Path:
    if SEED_DB.is_file():
        return SEED_DB
    local = SITE_DIR / "instance_seed" / "league_of_legends.db"
    if local.is_file():
        return local
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["docker", "cp", f"{CONTAINER}:/opt/WebSyn/league_of_legends/"
                       f"instance_seed/league_of_legends.db", str(CACHE)],
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
             url_after: str | None = None):
        i = len(self.steps)
        before = f"step_{i:03d}.png"
        after = f"step_{i + 1:03d}.png"
        (self.shots_dir / after).write_bytes(PNG)
        self.steps.append({
            "step": i,
            "url": BASE + path if path.startswith("/") else path,
            "title": "League of Legends",
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

    def login(self, email: str):
        return (self.fill("/login/", email, "input[name=username]")
                    .fill("/login/", PASSWORD, "input[name=password]")
                    .step("/login/", "click", {"selector": "button[type=submit]"},
                          url_after="/account/"))

    def done(self, answer: str, final_path: str | None = None):
        if final_path:
            self.final_path = final_path
        self.step(self.final_path, "done", {"text": answer, "success": True})
        traj = {
                        "task_id": self.task_id,
            "task": next((t["ques"] for t in map(json.loads, (SITE_DIR / "tasks.jsonl").read_text().splitlines()) if t["id"] == self.task_id), "unknown task"),
            "start_url": self.start_url,
            "model": "review-fixture",
            "max_steps": 80,
            "steps": self.steps,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (self.final_path if self.final_path.startswith("/")
                                 else "/" + self.final_path),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return self.root


def build_run(root: Path, task_id: str, steps: list[tuple], answer: str,
              start_path: str = "/") -> Path:
    """steps: list of (path, action, params[, url_after]) tuples."""
    rb = RunBuilder(root, task_id, start_path)
    for entry in steps:
        path, action, params = entry[0], entry[1], entry[2]
        url_after = entry[3] if len(entry) > 3 else None
        rb.step(path, action, params, url_after=url_after)
    return rb.done(answer)


def noop_run(root: Path, task_id: str) -> Path:
    return build_run(root, task_id, [("/", "click", {"selector": "body"})], "")


def copy_db(seed: Path, dest: Path) -> Path:
    shutil.copy2(seed, dest)
    return dest


def mutate_db(seed: Path, dest: Path, statements: list[str]) -> Path:
    """Copy the seed and apply SQL statements (committed)."""
    copy_db(seed, dest)
    con = sqlite3.connect(dest)
    try:
        for statement in statements:
            con.execute(statement)
        con.commit()
    finally:
        con.close()
    return dest


def run_verifier(task_n: int, run_dir: Path, initial: Path, after: Path,
                 extra: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(VERIFY_DIR / f"verify_{task_n}.py"),
           "--run_dir", str(run_dir), "--initial_db", str(initial),
           "--after_db", str(after), "--no_llm", "True"]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(VERIFY_DIR), timeout=180)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"pass": False, "reason": f"parse_error rc={r.returncode}",
                "stdout": r.stdout[:200], "stderr": r.stderr[:200]}
