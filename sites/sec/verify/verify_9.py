#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--9 (sec).

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
 "task_id": "SEC.gov--9",
 "paths": [
  "/fast-answers\\?q=10-K",
  "/fast-answers/form10k",
  "/fast-answers\\?q=best\\+execution",
  "/fast-answers/bestex",
  "/fast-answers\\?q=Section\\+31",
  "/fast-answers/sec31",
  "/fast-answers\\?q=Ponzi",
  "/fast-answers/ponzi",
  "/fast-answers\\?q=proxy",
  "/fast-answers/proxy"
 ],
 "claims": [
  [
   "10-K window",
   "60 to 90 days"
  ],
  [
   "10-K origin",
   "fixture"
  ],
  [
   "best execution",
   "best execution reasonably available"
  ],
  [
   "best execution origin",
   "captured"
  ],
  [
   "Section 31 basis",
   "volume of securities( that are)? sold"
  ],
  [
   "Section 31 origin",
   "captured"
  ],
  [
   "Ponzi promise",
   "high returns with little or no risk"
  ],
  [
   "Ponzi origin",
   "fixture"
  ],
  [
   "proxy modified",
   "09/?08/?2011"
  ],
  [
   "proxy origin",
   "captured"
  ]
 ],
 "forbidden": [
  [
   "swapped origin tags",
   "10-?k[^;.]{0,120}origin[^;.]{0,20}captured|proxy[^;.]{0,120}origin[^;.]{0,20}fixture"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--9', SPEC))
