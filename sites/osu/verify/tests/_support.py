"""Shared seed helper for OSU verifier tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
SEED = SITE / "instance_seed" / "osu.db"


def ensure_seed() -> Path:
    if SEED.is_file():
        return SEED
    subprocess.run(
        [sys.executable, str(SITE / "migrate_seed.py")],
        cwd=SITE,
        check=True,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
    )
    return SEED
