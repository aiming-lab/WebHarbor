#!/usr/bin/env python3
"""Run the complete OSU verifier, application, and environment regression suite."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

REPO_ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO_ROOT))

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromNames([
  'sites.osu.verify.test_verifiers',
  'sites.osu.verify.test_environment_quality',
  'sites.osu.verify.test_app',
 ])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 raise SystemExit(0 if result.wasSuccessful() else 1)
