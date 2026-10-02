#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--18 (sec).

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
 "task_id": "SEC.gov--18",
 "paths": [
  "/resources-investors/investor-alerts-bulletins/crypto-asset",
  "/fast-answers/ponzi",
  "/edgar/full-text-search\\?q=digital\\+assets&forms=8-K",
  "/submit-tip-or-complaint/tcr-disclaimer",
  "/submit-tip-or-complaint/report-possible-securities-law-violations",
  "/submit-tip-or-complaint/confirmation/TCR-"
 ],
 "claims": [
  [
   "red flag 1",
   "guaranteed returns|celebrity endorsements|exclusive access"
  ],
  [
   "red flag 2",
   "crypto assets,?\\s*gift cards or wire transfers|recruits?\\s+you to bring in friends"
  ],
  [
   "Ponzi promise",
   "high returns with little or no risk"
  ],
  [
   "FTS total",
   "\\b5501\\b"
  ],
  [
   "top company",
   "volcon,?\\s*inc\\.?"
  ],
  [
   "TCR reference",
   "tcr-[a-z0-9]{8}"
  ]
 ],
 "forbidden": [
  [
   "wrong FTS total",
   "\\b(5500|5502|5510)\\b"
  ]
 ],
 "state": {
  "tips": {
   "added": [
    {
     "user_id": None,
     "name": "Jordan Lee",
     "email": "jordan.lee@test.com",
     "violation_type": "fraud",
     "subject_firm": None,
     "submitted_at": "2026-09-30",
     "reference": {
      "regex": "TCR-[A-Z0-9]{8}"
     },
     "details": {
      "min_len": 30
     }
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--18', SPEC))
