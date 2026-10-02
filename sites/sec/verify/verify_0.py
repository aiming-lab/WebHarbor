#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--0 (sec).

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
 "task_id": "SEC.gov--0",
 "paths": [
  "/edgar/company/0000320193\\?type=10-K",
  "/edgar/filing/0000320193/0000320193-25-000079",
  "/edgar/company/0000320193\\?type=10-Q",
  "/edgar/filing/0000320193/0000320193-26-000020",
  "/edgar/company/0001318605",
  "/login",
  "/account"
 ],
 "claims": [
  [
   "10-K filing date",
   "10-?k[^;]{0,200}2025-10-31|2025-10-31[^;]{0,80}10-?k"
  ],
  [
   "10-K period",
   "2025-09-27"
  ],
  [
   "10-K accession",
   "0000320193-25-000079"
  ],
  [
   "10-Q filing date",
   "10-?q[^;]{0,200}2026-07-31|2026-07-31[^;]{0,80}10-?q"
  ],
  [
   "10-Q period",
   "2026-06-27"
  ],
  [
   "10-Q accession",
   "0000320193-26-000020"
  ],
  [
   "longer period",
   "longer"
  ],
  [
   "watchlist count",
   "\\b3\\s+compan"
  ]
 ],
 "forbidden": [
  [
   "wrong watchlist count",
   "\\b2\\s+companies on (her|the) watchlist|\\b4\\s+compan"
  ]
 ],
 "state": {
  "watchlist_items": {
   "added": [
    {
     "user_id": 1,
     "cik": "0001318605",
     "added_at": "2026-09-30"
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--0', SPEC))
