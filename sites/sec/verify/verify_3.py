#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--3 (sec).

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
 "task_id": "SEC.gov--3",
 "paths": [
  "/edgar/company/0001318605\\?type=8-K",
  "/edgar/filing/0001318605/0001628280-26-063820",
  "/edgar/filing/0001318605/0001628280-26-063820/document",
  "/edgar/filing/0001318605/0001628280-26-049213",
  "/edgar/company/0001318605\\?type=4",
  "/edgar/filing/0001318605/0001104659-26-106432",
  "/edgar/company/0001318605\\?type=10-Q"
 ],
 "claims": [
  [
   "first 8-K date",
   "2026-09-29"
  ],
  [
   "first 8-K items",
   "1\\.01[\\s,]*1\\.02[\\s,]*2\\.03[\\s,]*(and[\\s,]+)?9\\.01"
  ],
  [
   "first 8-K accession",
   "0001628280-26-063820"
  ],
  [
   "first 8-K period",
   "8-?k[^;]{0,200}period of report is 2026-09-29"
  ],
  [
   "second 8-K date",
   "2026-07-22"
  ],
  [
   "second 8-K items",
   "2\\.02[\\s,]*(and[\\s,]+)?9\\.01"
  ],
  [
   "second 8-K accession",
   "0001628280-26-049213"
  ],
  [
   "second 8-K period",
   "period of report is 2026-07-22"
  ],
  [
   "shared items",
   "9\\.01"
  ],
  [
   "primary document filename",
   "tsla-20260929\\.htm"
  ],
  [
   "Form 4 count",
   "\\b5\\s+form\\s?4s?\\b|form\\s?4[^.]{0,60}\\b5\\b"
  ],
  [
   "newest Form 4 period",
   "2026-09-05"
  ],
  [
   "10-Q count",
   "\\b4\\s+10-?qs?\\b|10-?q[^.]{0,60}\\b4\\b"
  ]
 ],
 "forbidden": [
  [
   "wrong Form 4 count",
   "\\b[46-9]\\s+form\\s?4s?\\b"
  ],
  [
   "wrong first period",
   "most recent[^;]{0,200}period of report is 2026-(?!09-29)[0-9-]+"
  ],
  [
   "wrong next period",
   "next 8-?k[\\s\\S]{0,120}period of report is 2026-(?!07-22)[0-9-]+"
  ],
  [
   "wrong Form 4 period",
   "form\\s?4[^;.]{0,80}period of report is 2026-(?!09-05)[0-9-]+"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--3', SPEC))
