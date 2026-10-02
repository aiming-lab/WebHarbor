#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--10 (sec).

Ground truth frozen from the reviewer's honest two-round Chromium walks of
orch/contribute/sec @ b1447395 (review container webharbor:sec-review2,
per-task control-plane reset + fresh context; evidence tree
wh-sec-r2-evidence/runs/round1|2; every walked fact independently
cross-checked against the frozen in-image seed database; task text deepened
by the NEEDS-FIX round and re-walked by the reviewer).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_lib  # noqa: E402

SPEC = {
 "task_id": "SEC.gov--10",
 "paths": [
  "/investor-alerts-bulletins/ponzi-schemes",
  "/investor-alerts-bulletins/fees",
  "/investor-alerts-bulletins/cold-call",
  "/investor-alerts-bulletins/municipal",
  "investor-alerts-bulletins\\?kind=&q=risks",
  "investor-alerts-bulletins\\?kind=bulletin",
  "investor-alerts-bulletins\\?kind=alert"
 ],
 "claims": [
  [
   "Ponzi date",
   "aug\\.?\\s*12,?\\s*2026"
  ],
  [
   "warning sign 1",
   "high returns with little or no risk"
  ],
  [
   "warning sign 2",
   "overly consistent returns"
  ],
  [
   "fee cost",
   "quarter of your final balance"
  ],
  [
   "fee type",
   "sales loads|management expense ratios"
  ],
  [
   "cold flag 1",
   "refuses to send"
  ],
  [
   "cold flag 2",
   "demands an immediate decision"
  ],
  [
   "municipal date",
   "apr\\.?\\s*14,?\\s*2026"
  ],
  [
   "municipal risk",
   "credit risk"
  ],
  [
   "risks search count",
   "risks?[^.]{0,60}\\b2\\s+items?\\b"
  ],
  [
   "bulletin count",
   "bulletins?[^.]{0,60}\\b3\\s+items?\\b"
  ],
  [
   "alert count",
   "alerts?[^.]{0,60}\\b6\\s+items?\\b"
  ]
 ],
 "forbidden": [
  [
   "wrong bulletin count",
   "bulletins?[^.]{0,60}\\b(2|4-9|1\\d)\\s+items?\\b"
  ],
  [
   "wrong alert count",
   "alerts?[^.]{0,60}\\b(3-5|7-9|1\\d|2)\\s+items?\\b"
  ],
  [
   "wrong risks count",
   "risks?[^.]{0,60}\\b(3-9|1\\d)\\s+items?\\b"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--10', SPEC))
