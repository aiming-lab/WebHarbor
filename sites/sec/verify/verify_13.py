#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--13 (sec).

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
 "task_id": "SEC.gov--13",
 "paths": [
  "/login",
  "/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional",
  "/submit-tip-or-complaint/complaint-confirmation/IC-",
  "/account"
 ],
 "claims": [
  [
   "complaint reference",
   "ic-[a-z0-9]{8}"
  ],
  [
   "account firm",
   "granite harbor capital llc"
  ]
 ],
 "forbidden": [
  [
   "fake reference",
   "ic-0{8}|ic-12345678"
  ]
 ],
 "state": {
  "complaints": {
   "added": [
    {
     "user_id": 1,
     "name": "Alice Johnson",
     "email": "alice.j@test.com",
     "your_role": "individual investor",
     "issue_type": "unauthorized trading",
     "subject_firm": "Granite Harbor Capital LLC",
     "subject_person": "T. Brooks",
     "subject_ticker": "GRHN",
     "submitted_at": "2026-09-30",
     "reference": {
      "regex": "IC-[A-Z0-9]{8}"
     },
     "address": {
      "min_len": 5
     },
     "phone": {
      "min_len": 7
     },
     "details": {
      "min_len": 20
     }
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--13', SPEC))
