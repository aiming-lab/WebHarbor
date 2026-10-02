#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--8 (sec).

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
 "task_id": "SEC.gov--8",
 "paths": [
  "/submit-filings/forms-index\\?q=10-K",
  "/submit-filings/forms-index\\?q=8-K",
  "/submit-filings/forms-index\\?q=1-A",
  "filed_by=Public\\+Companies",
  "statute=Securities\\+Act\\+of\\+1933"
 ],
 "claims": [
  [
   "10-K description",
   "annual report pursuant to section 13 or 15\\(d\\)"
  ],
  [
   "10-K SEC number",
   "sec1673"
  ],
  [
   "10-K updated",
   "feb\\.?\\s*2025"
  ],
  [
   "8-K SEC number",
   "sec873"
  ],
  [
   "1-A SEC number",
   "sec486"
  ],
  [
   "1-A statute",
   "securities act of 1933"
  ],
  [
   "public count",
   "\\b18\\s+forms?\\b"
  ],
  [
   "statute count",
   "\\b30\\s+forms?\\b"
  ],
  [
   "pdf served",
   "served|true|download|form10-k\\.pdf"
  ]
 ],
 "forbidden": [
  [
   "wrong public count",
   "\\b(0|1|17|19|2\\d|3[1-9]|[4-9]\\d)\\s+forms?\\b"
  ],
  [
   "wrong statute count",
   "\\b(29|31)\\s+forms?\\b"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--8', SPEC))
