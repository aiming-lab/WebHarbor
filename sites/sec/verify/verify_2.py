#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--2 (sec).

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
 "task_id": "SEC.gov--2",
 "paths": [
  "/edgar/company/0000789019\\?type=DEF\\+14A",
  "/edgar/filing/0000789019/0001193125-25-245150",
  "/edgar/company/0000789019\\?type=8-K",
  "/login",
  "/account"
 ],
 "claims": [
  [
   "Microsoft CIK",
   "0000789019"
  ],
  [
   "Microsoft SIC",
   "7372[^0-9]{0,80}prepackaged software"
  ],
  [
   "Microsoft state",
   "\\bwa\\b"
  ],
  [
   "Microsoft category",
   "large accelerated filer"
  ],
  [
   "DEF 14A date",
   "def\\s?14a|proxy[^.]{0,120}2025-10-21|2025-10-21"
  ],
  [
   "DEF 14A accession",
   "0001193125-25-245150"
  ],
  [
   "8-K count",
   "\\b6\\s+8-?ks?\\b|8-?k[^.]{0,60}\\b6\\b"
  ],
  [
   "watchlist count",
   "\\b3\\s+compan"
  ]
 ],
 "forbidden": [
  [
   "wrong 8-K count",
   "\\b[57-9]\\s+8-?ks?\\b"
  ]
 ],
 "state": {
  "watchlist_items": {
   "added": [
    {
     "user_id": 2,
     "cik": "0000789019",
     "added_at": "2026-09-30"
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--2', SPEC))
