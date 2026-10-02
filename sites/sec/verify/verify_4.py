#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--4 (sec).

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
 "task_id": "SEC.gov--4",
 "paths": [
  "/enforcement-litigation/litigation-releases\\?q=Asudani",
  "/enforcement-litigation/litigation-releases/lr-26662",
  "/enforcement-litigation/litigation-releases\\?q=Noble",
  "/enforcement-litigation/litigation-releases/lr-26660",
  "/enforcement-litigation/administrative-proceedings\\?q=Brown"
 ],
 "claims": [
  [
   "Asudani number",
   "lr-?26662"
  ],
  [
   "Asudani date",
   "sept\\.?\\s*30,?\\s*2026|september\\s*30,?\\s*2026"
  ],
  [
   "court",
   "s\\.?d\\.?n\\.?y\\.?"
  ],
  [
   "acquisition",
   "supernus[^.]{0,80}adamas|adamas pharmaceuticals"
  ],
  [
   "document label",
   "sec complaint"
  ],
  [
   "document opens",
   "opens|served|download"
  ],
  [
   "Brown/Grant/Noble number",
   "lr-?26660"
  ],
  [
   "Noble total",
   "1,?074,?984\\.36"
  ],
  [
   "Brown admin release",
   "34-106553"
  ],
  [
   "Brown admin file number",
   "3-22766"
  ]
 ],
 "forbidden": [
  [
   "wrong Noble total",
   "731,?281|293,?703|50,?000\\.00\\b(?!.{0,40}total)|2,?680,?732"
  ]
 ],
 "state": {}
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--4', SPEC))
