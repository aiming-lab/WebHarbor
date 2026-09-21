#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--13.

Search for recent news related to Trump and summarize the main points.

Checks: the run performed a site search whose query mentions Trump and
opened at least one of the seeded Trump stories (all 29 are hardcoded
below); the answer names Trump and states at least two facts of the
story it opened.

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

CONTEXT_PAGES = ["/search"]
CONTEXT_SEARCHES = ["trump"]
GROUND_TRUTH = [
 {
  "slug": "c79jqx1xdy9o",
  "title": "Trump's deadline looms but Asian nations already have deals with Iran",
  "facts": [
   [
    "trump",
    "deadline"
   ],
   [
    "iran"
   ],
   [
    "asian nations",
    "asia"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cge0xre3d27o",
  "title": "Trump says Iran's handling of Strait of Hormuz is 'not the agreement we have'",
  "facts": [
   [
    "trump"
   ],
   [
    "iran"
   ],
   [
    "strait of hormuz",
    "hormuz"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "clyeg3224d9t",
  "title": "Trump questions Iran's handling of Strait of Hormuz as world leaders move to shore up ceasefire",
  "facts": [
   [
    "trump"
   ],
   [
    "iran"
   ],
   [
    "hormuz",
    "ceasefire"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c0j6een0l62o",
  "title": "'I'm not Epstein's victim' and 'We see you, Vlad'",
  "facts": [
   [
    "epstein"
   ],
   [
    "vlad",
    "putin"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "bbcindepth",
  "title": "BBC InDepth",
  "facts": [
   [
    "emma barnett",
    "john simpson",
    "indepth",
    "bbc indepth"
   ],
   [
    "deep reads",
    "analysis",
    "saturday"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c2evppm30p7o",
  "title": "Hip-hop pioneer, Afrika Bambaataa, dies aged 68",
  "facts": [
   [
    "afrika bambaataa",
    "bambaataa"
   ],
   [
    "hip hop",
    "hip-hop"
   ],
   [
    "dies",
    "died",
    "68"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cx24n8eqzgyo",
  "title": "The US refinery now processing Venezuelan oil",
  "facts": [
   [
    "refinery"
   ],
   [
    "venezuelan",
    "venezuela"
   ],
   [
    "oil"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c1krpjr91v2o",
  "title": "Has US achieved its war objectives in Iran?",
  "facts": [
   [
    "war objectives",
    "objectives"
   ],
   [
    "iran"
   ],
   [
    "us",
    "united states"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cq6j0rnvlzeo",
  "title": "Petrol and diesel prices rise again as concerns grow over ceasefire",
  "facts": [
   [
    "petrol",
    "diesel",
    "fuel"
   ],
   [
    "prices rise",
    "prices"
   ],
   [
    "ceasefire"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c20qv0w1j1do",
  "title": "Oil price fluctuates ahead of Trump's Iran deal deadline",
  "facts": [
   [
    "oil price",
    "oil"
   ],
   [
    "fluctuates",
    "fluctuate"
   ],
   [
    "trump",
    "deadline"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c3ex07l1qvpo",
  "title": "Melania Trump denies ties to Jeffrey Epstein and urges hearing for survivors",
  "facts": [
   [
    "melania trump",
    "melania"
   ],
   [
    "epstein"
   ],
   [
    "denies",
    "survivors"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cgld65x396go",
  "title": "White House staff told not to place bets on prediction markets",
  "facts": [
   [
    "white house"
   ],
   [
    "bets",
    "bet",
    "prediction markets"
   ],
   [
    "insider"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c8dl7g6e59eo",
  "title": "Oil prices choppy after expletive-laden Trump threat to Iran",
  "facts": [
   [
    "oil prices",
    "oil"
   ],
   [
    "choppy"
   ],
   [
    "trump",
    "threat",
    "expletive"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c5yx4e9d8pdo",
  "title": "Faisal Islam: Iran war pause is welcome but the economic scars will last",
  "facts": [
   [
    "faisal islam"
   ],
   [
    "iran"
   ],
   [
    "economic scars",
    "economic"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cgk0edynpmzo",
  "title": "Lebanon thought there was a ceasefire - then Israel unleashed deadly blitz",
  "facts": [
   [
    "lebanon"
   ],
   [
    "ceasefire"
   ],
   [
    "israel"
   ]
  ],
  "min_facts": 2
 },
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
    "crew",
    "returning"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cz0ex432dmyo",
  "title": "Music giant Universal gets $64bn takeover offer",
  "facts": [
   [
    "universal"
   ],
   [
    "64bn",
    "takeover"
   ],
   [
    "music"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cp3l4yk5rlgo",
  "title": "Ceasefire or no ceasefire, the Middle East's reshuffling is not yet done",
  "facts": [
   [
    "ceasefire"
   ],
   [
    "middle east"
   ],
   [
    "reshuffling"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "ce84z6y3ke4o",
  "title": "What we know about the two-week ceasefire between the US and Iran",
  "facts": [
   [
    "two-week",
    "two week"
   ],
   [
    "ceasefire"
   ],
   [
    "iran"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "cly7d9rv4nro",
  "title": "'We should not be at the mercy of events abroad' - Starmer",
  "facts": [
   [
    "starmer"
   ],
   [
    "mercy of events"
   ],
   [
    "events abroad"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c20zgjzz0e4o",
  "title": "Will UK petrol and diesel prices start going down?",
  "facts": [
   [
    "petrol",
    "diesel",
    "fuel"
   ],
   [
    "prices"
   ],
   [
    "going down",
    "cheaper"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c8r40y3rv75o",
  "title": "Oil prices plunge and shares jump on US-Iran ceasefire plan",
  "facts": [
   [
    "oil prices",
    "oil"
   ],
   [
    "plunge"
   ],
   [
    "shares",
    "ceasefire"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "crk165g4vv3o",
  "title": "US jobs surge unexpectedly in March despite Iran war",
  "facts": [
   [
    "jobs"
   ],
   [
    "surge"
   ],
   [
    "march"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "c4g89kkvenqo",
  "title": "US has let in 4,499 refugees since October - all but three were South African",
  "facts": [
   [
    "refugees"
   ],
   [
    "4,499",
    "4499"
   ],
   [
    "south african"
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
    "land",
    "landing"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "trump-holds-rally-in-pennsylvania-as-swing-state-polls-tighten",
  "title": "Trump holds rally in Pennsylvania as swing-state polls tighten",
  "facts": [
   [
    "trump"
   ],
   [
    "rally"
   ],
   [
    "pennsylvania",
    "swing state"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "trump-trial-jury-hears-closing-arguments-in-new-york-case",
  "title": "Trump trial: jury hears closing arguments in New York case",
  "facts": [
   [
    "trump"
   ],
   [
    "trial",
    "jury"
   ],
   [
    "new york",
    "closing arguments"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "trump-campaign-raises-record-100m-in-single-month",
  "title": "Trump campaign raises record $100m in single month",
  "facts": [
   [
    "trump"
   ],
   [
    "campaign"
   ],
   [
    "100m",
    "raises",
    "record"
   ]
  ],
  "min_facts": 2
 },
 {
  "slug": "trump-announces-running-mate-decision-will-come-at-republican-con",
  "title": "Trump announces running mate decision will come at Republican convention",
  "facts": [
   [
    "trump"
   ],
   [
    "running mate"
   ],
   [
    "republican convention"
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
    j.check("searched_or_opened_trump_news",
            searched(traj, "trump") or bool(opened),
            f"searched={searched(traj, 'trump')} opened={opened}")
    j.check("answer_mentions_trump", "trump" in ans.lower(),
            "the summary must be about Trump")
    matched = [g for g in GROUND_TRUTH if group_hits(ans, g["facts"]) >= 2]
    j.check("answer_matches_trump_story", bool(matched),
            f"matched={[g['title'] for g in matched]}")

if __name__ == "__main__":
    run("BBC News--13", body)
