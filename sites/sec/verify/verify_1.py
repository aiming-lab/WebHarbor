#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--1 (sec).

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
 "task_id": "SEC.gov--1",
 "paths": [
  "/edgar/full-text-search\\?q=artificial\\+intelligence&forms=10-K",
  "/edgar/full-text-search\\?q=artificial\\+intelligence&forms=8-K",
  "/edgar/full-text-search\\?q=artificial\\+intelligence&forms=10-K&datea=2020-01-01",
  "/edgar/company/0000320193",
  "/edgar/company/0000320193\\?type=10-K",
  "/edgar/filing/0000320193/0000320193-25-000079"
 ],
 "claims": [
  [
   "10-K total",
   "10-?k[^.]{0,80}10000|10000[^.]{0,80}10-?k"
  ],
  [
   "top result company",
   "artificial intelligence technology solutions"
  ],
  [
   "top result CIK",
   "0001498148"
  ],
  [
   "top result filing date",
   "0001161697-21-000289|2021-06-01"
  ],
  [
   "8-K total",
   "8-?k[^.]{0,80}10000|10000[^.]{0,80}8-?k"
  ],
  [
   "narrowed count",
   "(2020-01-01|narrowed)[^.]{0,80}\\b7\\s+documents?\\b"
  ],
  [
   "Apple 10-K count",
   "\\b3\\s+10-?k\\s+filings?\\b"
  ],
  [
   "Apple newest 10-K date",
   "2025-10-31"
  ],
  [
   "Apple CIK",
   "0000320193"
  ],
  [
   "Apple 10-K period",
   "2025-09-27"
  ]
 ],
 "forbidden": [
  [
   "wrong Apple 10-K count",
   "\\b[124-9]\\s+10-?ks?\\b(?!\\d)"
  ],
  [
   "wrong narrowed count",
   "(2020-01-01|narrowed)[^.]{0,80}\\b(6|8|9|1\\d)\\s+documents?\\b"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--1', SPEC))
