"""Shared test setup for generated OSU seed assets."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / 'instance_seed' / 'osu.db'


def ensure_seed():
    if SEED.is_file():
        return SEED
    subprocess.run([sys.executable, '-c', 'import app'], cwd=SITE, check=True, capture_output=True, text=True)
    SEED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SITE / 'instance' / 'osu.db', SEED)
    shutil.rmtree(SITE / 'instance')
    return SEED
