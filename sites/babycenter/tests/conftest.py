from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


SITE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(tempfile.mkdtemp(prefix="babycenter-tests-"))
os.environ["BABYCENTER_DATABASE_URI"] = f"sqlite:///{TEST_ROOT / 'babycenter.db'}"
sys.path.insert(0, str(SITE_DIR))

import app as babycenter_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_root():
    yield
    with babycenter_app.app.app_context():
        babycenter_app.db.session.remove()
        babycenter_app.db.engine.dispose()
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


@pytest.fixture()
def client():
    babycenter_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with babycenter_app.app.test_client() as test_client:
        yield test_client
