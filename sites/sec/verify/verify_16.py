#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--16 (sec).

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
 "task_id": "SEC.gov--16",
 "paths": [
  "/signup",
  "/edgar/company/0001652044",
  "/login",
  "/account"
 ],
 "claims": [
  [
   "Alphabet CIK",
   "0001652044"
  ],
  [
   "Alphabet SIC",
   "7370[^0-9]{0,80}computer programming"
  ],
  [
   "watchlist company",
   "alphabet inc\\.?"
  ],
  [
   "watchlist ticker",
   "\\bgoogl\\b"
  ]
 ],
 "forbidden": [
  [
   "wrong CIK",
   "\\b000165204[0-35-9]\\b"
  ]
 ],
 "state": {
  "users": {
   "added": [
    {
     "email": "jordan.lee@test.com",
     "name": "Jordan Lee",
     "joined": "2026-09-30",
     "password_hash": {
      "bcrypt_password": "Jordan2026Pass"
     }
    }
   ]
  },
  "watchlist_items": {
   "added": [
    {
     "user_id": 5,
     "cik": "0001652044",
     "added_at": "2026-09-30"
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--16', SPEC))
