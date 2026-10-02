#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--11 (sec).

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
 "task_id": "SEC.gov--11",
 "paths": [
  "rulemaking-activity\\?q=Interval\\+Fund\\+Modernization",
  "rulemaking-activity\\?q=S7-2026-34",
  "status=Proposed\\+Rule",
  "status=Final\\+Rule",
  "q=quorum",
  "q=electronic\\+delivery"
 ],
 "claims": [
  [
   "interval date",
   "sept\\.?\\s*30,?\\s*2026"
  ],
  [
   "interval file number",
   "s7-2026-34"
  ],
  [
   "interval releases",
   "33-11444,\\s*34-106534,\\s*ic-36351"
  ],
  [
   "file lookup count",
   "\\b1\\s+(item|result|match)\\b"
  ],
  [
   "proposed count",
   "\\b18\\s+(items?|rules?)\\b"
  ],
  [
   "final count",
   "\\b28\\s+(items?|rules?)\\b"
  ],
  [
   "quorum date",
   "sept\\.?\\s*30,?\\s*2026"
  ],
  [
   "quorum release",
   "34-106537"
  ],
  [
   "e-delivery file number",
   "s7-2026-25"
  ],
  [
   "e-delivery date",
   "july\\s*16,?\\s*2026"
  ],
  [
   "total",
   "\\b49\\s+(items?|rulemaking items?)\\b"
  ]
 ],
 "forbidden": [
  [
   "wrong proposed count",
   "\\b(17|19)\\s+items?\\b"
  ],
  [
   "wrong final count",
   "\\b(27|29)\\s+items?\\b"
  ],
  [
   "wrong total",
   "\\b(48|50)\\s+items?\\b"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--11', SPEC))
