#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--6 (sec).

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
 "task_id": "SEC.gov--6",
 "paths": [
  "/enforcement-litigation/trading-suspensions\\?q=Happy\\+City",
  "/resources-investors/investor-alerts-bulletins/cold-call",
  "/fast-answers/pump",
  "/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional",
  "/submit-tip-or-complaint/complaint-confirmation/IC-"
 ],
 "claims": [
  [
   "suspension date",
   "june\\s*11,?\\s*2026"
  ],
  [
   "release number",
   "34-105675"
  ],
  [
   "red flag 1",
   "refuses to send written information"
  ],
  [
   "red flag 2",
   "demands an immediate decision|promises guaranteed returns|offer is\\s*'?'?confidential"
  ],
  [
   "pump answer",
   "dump\\s+(their\\s+)?shares at the inflated price"
  ],
  [
   "complaint reference",
   "ic-[a-z0-9]{8}"
  ]
 ],
 "forbidden": [
  [
   "wrong suspension date",
   "june\\s*1[02],\\s*2026|july\\s*11,\\s*2026"
  ]
 ],
 "state": {
  "complaints": {
   "added": [
    {
     "user_id": None,
     "name": "Maria Lopez",
     "email": "maria.lopez@example.com",
     "your_role": "individual investor",
     "issue_type": "misrepresentation or omission",
     "subject_firm": "Happy City Holdings Limited",
     "submitted_at": "2026-09-30",
     "reference": {
      "regex": "IC-[A-Z0-9]{8}"
     }
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--6', SPEC))
