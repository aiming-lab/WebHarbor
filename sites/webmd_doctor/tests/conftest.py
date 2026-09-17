"""Shared test bootstrap for the WebMD Doctor mirror.

``instance_seed/webmd_doctor.db`` is a build-time artifact (``.build-generated-seed``):
the Docker build regenerates it with ``seed_data.py`` and the pinned Hugging Face
tarball does not carry it. A reviewer who only ran ``scripts/fetch_assets.sh`` must
still be able to run this suite, so the frozen seed is rebuilt once per session
when it is absent, and the runtime copy the app binds (``instance/``, installed by
``websyn_start.sh`` at container boot) is created from it when missing. This
mirrors the autouse-fixture convention of the Walmart Careers mirror.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
SEED = SITE / "instance_seed" / "webmd_doctor.db"
RUNTIME = SITE / "instance" / "webmd_doctor.db"

# The app bootstraps its runtime database on import; this suite installs the
# frozen seed itself so both artifacts stay byte-identical.
os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture(scope="session", autouse=True)
def frozen_seed() -> None:
    if not SEED.is_file():
        import seed_data

        seed_data.build_seed_database()
    assert SEED.is_file(), f"seed_data.build_seed_database() did not produce {SEED}"
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    if not RUNTIME.is_file():
        shutil.copy2(SEED, RUNTIME)
