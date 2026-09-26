"""Shared fixtures for the parkers mirror test suite.

The module-level scratch DB is created (as a copy of the shipped seed)
and exported as PARKERS_DB_PATH *before* the app module is first
imported by any test module, so every test — including write paths
(login, shortlist, saved valuations, owner reviews) — runs against a
throwaway copy and never mutates the real instance DB. The suite is
therefore fully repeatable.
"""
import os
import pathlib
import shutil
import sys
import tempfile

import pytest

SITE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SITE))

os.environ.setdefault("FLASK_SECRET_KEY", "parkers-mirror-test")

_SEED = SITE / "instance_seed" / "parkers.db"
_SCRATCH_DIR = tempfile.mkdtemp(prefix="parkers-test-db-")
_SCRATCH = pathlib.Path(_SCRATCH_DIR) / "parkers.db"
if _SEED.exists():
    shutil.copyfile(_SEED, _SCRATCH)
else:  # pre-seed bootstrap builds it in place
    _SCRATCH.touch()
os.environ["PARKERS_DB_PATH"] = str(_SCRATCH)
