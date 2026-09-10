"""Shared current-seed and end-to-end verifier fixtures."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

VERIFY_DIR = Path(__file__).resolve().parent
SITE = VERIFY_DIR.parent
SEED = SITE / "instance_seed" / "compass.db"
BASE = "http://localhost:40022"


def ensure_seed() -> Path:
    current = False
    if SEED.is_file():
        try:
            with sqlite3.connect(SEED) as connection:
                row = connection.execute(
                    "SELECT version FROM seed_metadata WHERE id=1"
                ).fetchone()
                current = row == ("compass-source-v3",)
        except sqlite3.Error:
            current = False
    if not current:
        subprocess.run(
            [sys.executable, str(SITE / "migrate_seed.py"), str(SEED)],
            cwd=SITE,
            check=True,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
        )
    return SEED


def next_id(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f'SELECT COALESCE(MAX(id),0)+1 FROM "{table}"').fetchone()[0]


def make_run(root: Path, task: int, paths: list[str], answer: str, *, task_id: str | None = None, external: bool = False) -> Path:
    run = root / "run"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    steps = []
    urls = [("https://evil.invalid" if external else BASE) + path for path in paths]
    for index, current in enumerate(urls):
        following = urls[index + 1] if index + 1 < len(urls) else current
        before = f"step_{index:03d}_before.png"
        after = f"step_{index:03d}_after.png"
        Image.new("RGB", (390, 844), (240 - index % 20, 240, 240)).save(shots / before)
        Image.new("RGB", (390, 844), (238 - index % 20, 238, 238)).save(shots / after)
        steps.append({
            "url": current,
            "url_after": following,
            "action": "click",
            "screenshot_before": before,
            "screenshot_after": after,
        })
    trajectory = {
        "task_id": task_id or f"Compass--{task}",
        "start_url": BASE + "/",
        "steps": steps,
        "final_url": urls[-1] if urls else BASE + "/",
        "final_answer": answer,
        "terminated": True,
        "termination_reason": "agent_done",
    }
    (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def copied_databases(root: Path) -> tuple[Path, Path]:
    initial = root / "initial.db"
    after = root / "after.db"
    shutil.copy2(ensure_seed(), initial)
    shutil.copy2(ensure_seed(), after)
    return initial, after


def temporary_case():
    return tempfile.TemporaryDirectory(prefix="compass-verifier-")
