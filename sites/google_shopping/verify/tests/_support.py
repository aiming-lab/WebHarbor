"""Shared fixtures for the google_shopping verifier tests.

Snapshots are copies of the real deterministic seed (``instance_seed/google_shopping.db``,
rebuilt from the tracked source catalog by ``seed_data.py``; see ``.build-generated-seed``)
with mutations applied through sqlite, and trajectories are hand-written in the
``agent_demo/agent.py`` shape (step ``url`` = page before the action). No docker, no LLM.

Run from the agent_demo env so ``simpleArgParser`` (and Pillow) are importable:

    cd agent_demo && uv run python -m pytest ../sites/google_shopping/verify/tests -q
"""
from __future__ import annotations

import json
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
SEED_DB = SITE_DIR / "instance_seed" / "google_shopping.db"
BASE = "http://localhost:40084"
PASSWORD = "TestPass123!"

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
            "title": "Google Shopping",
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

    def login(self, email: str, display_name: str):
        return (self.step("/login", "fill", {"text": email, "selector": "input[name=email]"})
                    .step("/login", "fill", {"text": PASSWORD, "selector": "input[name=password]"})
                    .step("/login", "click", {"selector": ".auth-card button[type=submit]"}))

    def done(self, answer: str, final_path: str | None = None):
        self.final_answer = answer
        if final_path:
            self.final_path = final_path
        return self

    def write(self) -> Path:
        traj = {
            "task": next(json.loads(line)['ques'] for line in (SITE_DIR / 'tasks.jsonl').read_text().splitlines() if json.loads(line)['id'] == self.task_id),
            "task_id": self.task_id,
            "start_url": self.start_url,
            "model": "review-fixture",
            "max_steps": 60,
            "steps": self.steps,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": self.final_answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": BASE + (self.final_path if self.final_path.startswith("/") else "/"),
            "success_self_report": True,
        }
        (self.root / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return self.root


def build_run(root: Path, task_id: str, paths_and_actions, answer: str,
              login: tuple[str, str] | None = None, start_path: str = "/") -> Path:
    """Compact helper: sequence of (path, action, params) + final answer."""
    b = RunBuilder(root, task_id, start_path=start_path)
    if login:
        b.login(login[0], login[1])
    for item in paths_and_actions:
        path, action, params = (item + (None,))[:3] if len(item) < 3 else item
        b.step(path, action or "click", params or {})
    b.done(answer)
    return b.write()


def noop_run(root: Path, task_id: str) -> Path:
    """The no-op run: open the homepage, do nothing, empty answer, clean DB."""
    b = RunBuilder(root, task_id)
    b.step("/", "click", {"selector": "body"})
    b.done("")
    return b.write()


# ------------------------------------------------------------------ DB snapshots
def copy_db(target: Path) -> Path:
    shutil.copyfile(SEED_DB, target)
    return target


def mutate_db(target: Path, statements: list[tuple[str, tuple]]) -> Path:
    con = sqlite3.connect(str(target))
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return target


# ------------------------------------------------------------------ verifier runner
def run_verifier(task_n: int, run_dir: Path, initial_db: Path, after_db: Path,
                 container: str | None = None) -> dict:
    script = VERIFY_DIR / f"verify_{task_n}.py"
    cmd = [sys.executable, str(script), "--run_dir", str(run_dir),
           "--initial_db", str(initial_db), "--after_db", str(after_db), "--no_llm", "True"]
    if container:
        cmd += ["--container", container]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(VERIFY_DIR), timeout=120)
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"_parse_error": True, "stdout": r.stdout[:400], "stderr": r.stderr[:400],
                "returncode": r.returncode, "pass": False}
    verdict["_returncode"] = r.returncode
    return verdict
