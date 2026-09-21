#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--24.

Latest article about space exploration and its key points.

AUDIT NOTE (flagged in REPORT.md): 'latest space exploration article'
is ambiguous across the seeded Artemis/Moon/space stories of 12-14 Apr
2026 — any of the ten below is a defensible 'latest' pick, so the
contract grades the story the agent actually opened. Checks: opened one
of the ten; the answer summarizes that story's facts.

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

CONTEXT_PAGES = ["/news/science", "/latest"]
CONTEXT_SEARCHES = ["space", "space exploration", "nasa"]
GROUND_TRUTH = [
 {
  "slug": "c70dr45dj1lo",
  "title": "Artemis crew returning to Earth with 'all the good stuff' from Moon discoveries",
  "facts": [
   [
    "artemis"
   ],
   [
    "moon"
   ],
   [
    "orion",
    "splash down",
    "splashdown",
    "returning"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c6270030neyo",
  "title": "Nasa announces change to its Moon landing plans",
  "facts": [
   [
    "nasa"
   ],
   [
    "artemis"
   ],
   [
    "moon landing",
    "lunar landing",
    "low-earth orbit"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cz90yp7w104o",
  "title": "'We go for all humanity' - emotional moment as Artemis II blasts off",
  "facts": [
   [
    "artemis"
   ],
   [
    "florida"
   ],
   [
    "sls",
    "space launch system",
    "blast"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cj60nkd8nrko",
  "title": "Has Artemis II shown we can land on the Moon again?",
  "facts": [
   [
    "artemis"
   ],
   [
    "moon"
   ],
   [
    "landing",
    "2028"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "ckgrw045pg7o",
  "title": "Nasa's Artemis Moon rocket rolls back to pad for possible April launch",
  "facts": [
   [
    "space launch system",
    "sls",
    "moon rocket"
   ],
   [
    "kennedy",
    "pad 39b",
    "launch pad"
   ],
   [
    "april",
    "helium"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "nasa-confirms-europa-clipper-will-launch-this-autumn-on-mission-to-jup",
  "title": "NASA confirms Europa Clipper will launch this autumn on mission to Jupiter's icy moon",
  "facts": [
   [
    "europa clipper",
    "europa"
   ],
   [
    "jupiter"
   ],
   [
    "autumn",
    "icy moon"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "china-s-lunar-sample-mission-returns-rocks-from-the-far-side-of-the-mo",
  "title": "China's lunar sample mission returns rocks from the far side of the Moon",
  "facts": [
   [
    "china",
    "chang e",
    "chang'e"
   ],
   [
    "far side"
   ],
   [
    "moon rocks",
    "lunar sample",
    "samples"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "astronomers-detect-strongest-signs-yet-of-life-on-distant-exoplanet-k2",
  "title": "Astronomers detect strongest signs yet of life on distant exoplanet K2-18b",
  "facts": [
   [
    "k2-18b",
    "exoplanet"
   ],
   [
    "james webb"
   ],
   [
    "life"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "spacex-starship-completes-first-successful-orbital-refuelling-test",
  "title": "SpaceX Starship completes first successful orbital refuelling test",
  "facts": [
   [
    "starship",
    "spacex"
   ],
   [
    "refuelling",
    "refueling"
   ],
   [
    "moon and mars",
    "orbital"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cd9gwdgg38vo",
  "title": "Nasa spacecraft weighing 1,300lb re-enters Earth's atmosphere",
  "facts": [
   [
    "van allen"
   ],
   [
    "re-enter",
    "re-entry",
    "reenters",
    "re-enters"
   ],
   [
    "spacecraft",
    "probe"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "starlink-launches-direct-to-phone-satellite-service-across-europe",
  "title": "Starlink launches direct-to-phone satellite service across Europe",
  "facts": [
   [
    "starlink",
    "spacex"
   ],
   [
    "direct-to-phone",
    "direct to phone"
   ],
   [
    "europe"
   ],
   [
    "smartphone",
    "satellite"
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
    run("BBC News--24", body)
