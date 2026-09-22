#!/usr/bin/env python3
"""Run the complete OSU verifier, application, and environment regression suite."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
