"""Shared deterministic seed setup for Rotten Tomatoes verifier tests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / 'instance_seed' / 'rotten_tomatoes.db'


def ensure_seed():
    if SEED.is_file():
        return SEED
    shutil.rmtree(SITE / 'instance', ignore_errors=True)
    subprocess.run([sys.executable, '-c', 'import app'], cwd=SITE, check=True,
                   capture_output=True, text=True, env={**os.environ, 'PYTHONHASHSEED': '0'})
    SEED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SITE / 'instance' / 'rotten_tomatoes.db', SEED)
    shutil.rmtree(SITE / 'instance')
    return SEED
