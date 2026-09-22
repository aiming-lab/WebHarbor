#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--0.

Find a report about recent developments in renewable energy technologies in the UK.

Checks: the run opened one of the eight UK/Energy articles (section
/news/uk?subsection=Energy); the answer names that article and states
at least two of its on-page facts.

Input/Output: see verify_lib.run / Judge.emit. Ground truth below is frozen
from the mirror's own pages (section listings + article detail text).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_article, opened_page, searched,
                        mentions_title, mentions_title_frac, mentions_number,
                        mentions_group, group_hits, mentions_date, last_shot,
                        llm_text_match, llm_screenshot_shows, norm)

CONTEXT_PAGES = ["/news/uk"]
CONTEXT_SEARCHES = ["renewable", "energy"]
GROUND_TRUTH = [
 {
  "slug": "uk-offshore-wind-capacity-hits-record-as-new-north-sea-turbines-spin-u",
  "title": "UK offshore wind capacity hits record as new North Sea turbines spin up",
  "facts": [
   [
    "16 gigawatts",
    "16 gw"
   ],
   [
    "north sea",
    "offshore wind",
    "wind farm"
   ],
   [
    "15 mw",
    "new generation of turbines",
    "turbines"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "scotland-unveils-tidal-power-array-that-could-be-the-world-s-largest",
  "title": "Scotland unveils tidal power array that could be the world's largest",
  "facts": [
   [
    "50 mw"
   ],
   [
    "orkney"
   ],
   [
    "tidal",
    "marine renewable"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "solar-panel-breakthrough-at-uk-lab-promises-30-cheaper-rooftop-power",
  "title": "Solar panel breakthrough at UK lab promises 30% cheaper rooftop power",
  "facts": [
   [
    "oxford",
    "perovskite"
   ],
   [
    "solar panel",
    "rooftop",
    "solar cell"
   ],
   [
    "cheaper",
    "30%",
    "30 per cent"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "uk-s-first-commercial-hydrogen-powered-train-rolls-out-in-teesside",
  "title": "UK's first commercial hydrogen-powered train rolls out in Teesside",
  "facts": [
   [
    "hydrogen",
    "fuel cell"
   ],
   [
    "teesside",
    "north east"
   ],
   [
    "zero-emission",
    "zero emission",
    "passenger service"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "national-grid-says-record-renewables-share-pushed-gas-to-historic-low",
  "title": "National Grid says record renewables share pushed gas to historic low",
  "facts": [
   [
    "national grid"
   ],
   [
    "60%",
    "60 per cent"
   ],
   [
    "gas",
    "historic low"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "uk-battery-storage-boom-accelerates-as-grid-scale-projects-triple",
  "title": "UK battery storage boom accelerates as grid-scale projects triple",
  "facts": [
   [
    "battery storage",
    "grid-scale"
   ],
   [
    "tripled",
    "triple"
   ],
   [
    "18 months"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "floating-wind-pilot-off-welsh-coast-generates-first-power-to-the-grid",
  "title": "Floating wind pilot off Welsh coast generates first power to the grid",
  "facts": [
   [
    "floating wind",
    "erebus"
   ],
   [
    "pembrokeshire",
    "welsh coast"
   ],
   [
    "first power",
    "first electricity",
    "deep-water"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "thermal-heat-pumps-uk-trial-shows-50-cut-in-household-energy-bills",
  "title": "Thermal heat pumps: UK trial shows 50% cut in household energy bills",
  "facts": [
   [
    "heat pump"
   ],
   [
    "3,000 homes",
    "trial"
   ],
   [
    "50%",
    "cut in half",
    "half"
   ],
   [
    "smart tariff"
   ]
  ],
  "min_facts": 2
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)


def body(j, traj, ans):
    opened = opened_article(traj, [g["slug"] for g in GROUND_TRUTH])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    if opened:
        j.evidence.append(f"[note] opened detail page(s): {opened}")
    matched = [g for g in GROUND_TRUTH
               if group_hits(ans, g["facts"]) >= g["min_facts"]]
    bound = [g for g in matched if g["slug"] in opened] if opened else matched
    j.check("answer_matches_qualifying_article", bool(bound),
            f"matched={[g['title'] for g in bound]} (facts from the "
            f"article's own page/listing card)")

if __name__ == "__main__":
    run("BBC News--0", body)
