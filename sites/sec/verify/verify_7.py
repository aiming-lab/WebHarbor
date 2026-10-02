#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--7 (sec).

Ground truth frozen from the reviewer's honest two-round Chromium walks of
orch/contribute/sec @ e7067e37 (review container webharbor:sec-review,
per-task control-plane reset + fresh context; evidence tree
wh-sec-review-evidence/runs/round1|2; every walked fact independently
cross-checked against the frozen in-image seed database).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_lib  # noqa: E402

SPEC = {
 "task_id": "SEC.gov--7",
 "paths": [
  "/newsroom/press-releases/2026-98-",
  "/newsroom/press-releases\\?q=veterans",
  "/newsroom/press-releases/2026-97-",
  "/newsroom/press-releases\\?q=Meyer",
  "/enforcement-litigation/litigation-releases\\?q=Meyer"
 ],
 "claims": [
  [
   "release number",
   "2026-98"
  ],
  [
   "release date",
   "sept\\.?\\s*30,?\\s*2026"
  ],
  [
   "investments",
   "spacex"
  ],
  [
   "forfeited amount",
   "\\$?\\s*3,?000,?000"
  ],
  [
   "veterans number",
   "2026-97"
  ],
  [
   "veterans scheme",
   "fraud scheme that raised more than \\$?\\s*8\\.7 million from 35 investors"
  ],
  [
   "Meyer search count",
   "\\b1\\s+(release|result|match|item)"
  ],
  [
   "litigation number",
   "lr-?26659"
  ],
  [
   "litigation respondents",
   "owen e\\.?\\s?h\\.?\\s*meyer and meyer global management llc"
  ]
 ],
 "forbidden": [
  [
   "wrong search count",
   "\\b[2-9]\\s+releases?\\b|\\b1[0-9]\\s+releases?\\b"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--7', SPEC))
