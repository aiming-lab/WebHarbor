#!/usr/bin/env python3
"""Deterministic reviewer verifier for task SEC.gov--12 (sec).

Ground truth frozen from the reviewer's honest two-round Chromium walks of
orch/contribute/sec @ b1447395 (review container webharbor:sec-review2,
per-task control-plane reset + fresh context; evidence tree
wh-sec-r2-evidence/runs/round1|2; every walked fact independently
cross-checked against the frozen in-image seed database; task text deepened
by the NEEDS-FIX round and re-walked by the reviewer — now includes the
footer press-release email subscription with its exact DB delta).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_lib  # noqa: E402

SPEC = {
 "task_id": "SEC.gov--12",
 "paths": [
  "/newsroom",
  "/newsroom/press-releases/2026-98-sec-charges-meyer-global",
  "/newsroom/speeches-statements\\?q=Trump",
  "/newsroom/whats-new",
  "/newsroom/press-releases\\?q=Zoe\\+Financial",
  "/newsroom/press-releases/2026-94-sec-charges-registered-investment-adviser",
  "/subscribe"
 ],
 "claims": [
  [
   "latest title",
   "sec charges meyer global management and its ceo"
  ],
  [
   "latest number",
   "2026-98"
  ],
  [
   "latest date",
   "sept\\.?\\s*30,?\\s*2026"
  ],
  [
   "pre-IPO company",
   "spacex"
  ],
  [
   "Trump results count",
   "\\b1\\s+results?\\b"
  ],
  [
   "Trump speaker",
   "divisions of investment management and corporation finance"
  ],
  [
   "whats-new 1",
   "mukesh asudani"
  ],
  [
   "whats-new 2",
   "robert bernardi and sunil chandra"
  ],
  [
   "Zoe charge",
   "failing to fully and fairly disclose material facts concerning conflicts of interest"
  ],
  [
   "Zoe number",
   "2026-94"
  ],
  [
   "Zoe date",
   "sept\\.?\\s*28,?\\s*2026"
  ],
  [
   "subscription confirmation",
   "news\\.fan@example\\.com[^.]*subscribed"
  ]
 ],
 "forbidden": [
  [
   "wrong Zoe number",
   "\\b2026-9[0-3579]\\b"
  ],
  [
   "wrong latest number",
   "\\b2026-9[79]\\b(?!.{0,80}meyer global management)"
  ]
 ],
 "state": {
  "email_subscriptions": {
   "added": [
    {
     "email": "news.fan@example.com",
     "topics": "press releases",
     "submitted_at": "2026-09-30"
    }
   ]
  }
 }
}

if __name__ == "__main__":
    raise SystemExit(verify_lib.main('SEC.gov--12', SPEC))
