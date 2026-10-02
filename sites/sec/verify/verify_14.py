#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--14 (sec).

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
 "task_id": "SEC.gov--14",
 "paths": [
  "/login",
  "/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization",
  "/submit-tip-or-complaint/question-confirmation/Q-",
  "/resources-investors/investor-alerts-bulletins/cold-call",
  "/subscribe"
 ],
 "claims": [
  [
   "question reference",
   "q-[a-z0-9]{8}"
  ],
  [
   "red flag",
   "refuses to send written information|demands an immediate decision|promises guaranteed returns|'confidential'"
  ],
  [
   "subscription",
   "now subscribed|subscribed"
  ]
 ],
 "forbidden": [
  [
   "fake reference",
   "q-0{8}|q-12345678"
  ]
 ],
 "state": {
  "questions": {
   "added": [
    {
     "name": "Carol Davis",
     "email": "carol.d@test.com",
     "topic": "investment professional",
     "submitted_at": "2026-09-30",
     "reference": {
      "regex": "Q-[A-Z0-9]{8}"
     },
     "question": {
      "min_len": 20
     }
    }
   ]
  },
  "email_subscriptions": {
   "added": [
    {
     "email": "updates.carol@example.com",
     "topics": "investor alerts",
     "submitted_at": "2026-09-30"
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--14', SPEC))
