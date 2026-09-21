#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--7.

AI-related story under Technology of Business: what is in the first
picture in the story.

The first picture on a bbc_news article page is its hero image. The four
Technology of Business AI stories and their frozen hero-image contents
(audited on the live mirror) are hardcoded below. Checks: opened one of
the four stories (via /news/business?subsection=Technology+of Business or
search); the answer states that story's facts; the answer describes the
frozen hero image via deterministic image keyword groups plus an
anchored LLM consistency check against the frozen description (skipped
under --no_llm).

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

CONTEXT_PAGES = ["/news/business"]
CONTEXT_SEARCHES = ["technology of business", "ai", "artificial intelligence"]
GROUND_TRUTH = [
 {
  "slug": "how-ai-is-quietly-reshaping-the-global-insurance-industry",
  "title": "How AI is quietly reshaping the global insurance industry",
  "facts": [],
  "min_facts": 0,
  "image_groups": [
   [
    "man",
    "speaker",
    "person"
   ],
   [
    "suit",
    "tie",
    "jacket"
   ],
   [
    "podium",
    "lectern",
    "microphone",
    "mic",
    "speaking",
    "addressing"
   ],
   [
    "flag",
    "american"
   ]
  ],
  "image_description": "A man in a dark suit and tie speaking at a podium with a microphone in front of him, with a partially visible American flag behind him."
 },
 {
  "slug": "ai-startups-raise-record-40bn-as-investors-bet-on-generative-tools",
  "title": "AI startups raise record $40bn as investors bet on generative tools",
  "facts": [],
  "min_facts": 0,
  "image_groups": [
   [
    "football",
    "soccer",
    "match",
    "player"
   ],
   [
    "question mark",
    "circle"
   ],
   [
    "jersey",
    "kit",
    "shirt"
   ]
  ],
  "image_description": "A football (soccer) match action shot: a player in a blue jersey whose head is covered by a large yellow circle with a black question mark, next to a player in a green-and-white kit."
 },
 {
  "slug": "can-ai-replace-call-centre-workers-inside-the-indian-contact-centre-ex",
  "title": "Can AI replace call-centre workers? Inside the Indian contact-centre experiment",
  "facts": [],
  "min_facts": 0,
  "image_groups": [
   [
    "plane",
    "jet",
    "aircraft",
    "taking off"
   ],
   [
    "indepth",
    "in depth",
    "bbc"
   ],
   [
    "smoke",
    "skyline",
    "city"
   ]
  ],
  "image_description": "A BBC News 'InDepth' graphic: a large white passenger jet taking off, angled upward, over a red background with dark smoke and a faint city skyline, with the BBC logo and the word INDEPTH."
 },
 {
  "slug": "ai-chip-shortage-drives-up-costs-for-manufacturers-worldwide",
  "title": "AI chip shortage drives up costs for manufacturers worldwide",
  "facts": [],
  "min_facts": 0,
  "image_groups": [
   [
    "man",
    "person"
   ],
   [
    "lab",
    "workshop",
    "workbench"
   ],
   [
    "smartphone",
    "phone",
    "holding"
   ],
   [
    "computer",
    "electronics",
    "forensics"
   ]
  ],
  "image_description": "A smiling man in a computer/electronics lab holding a smartphone in both hands, wearing a T-shirt that reads 'COMPUTER FORENSICS LAB', surrounded by workbenches with electronics equipment."
 }
]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
def body(j, traj, ans):
    opened = opened_article(traj, [g["slug"] for g in GROUND_TRUTH])
    j.check("opened_tob_ai_story", bool(opened), f"opened={opened}")
    j.check("browsed_task_context", _context_ok(traj),
            f"pages={CONTEXT_PAGES} searches={CONTEXT_SEARCHES}")
    if not opened:
        return
    g = next(x for x in GROUND_TRUTH if x["slug"] == opened[0])
    hits = group_hits(ans, g["image_groups"])
    j.check("answer_describes_first_picture", hits >= 2,
            f"image keyword groups hit={hits}/{len(g['image_groups'])} "
            f"(need 2) for {g['title']!r}")
    ok, ev = llm_text_match(ans, g["image_description"],
                            "What is in the first picture of this story?")
    j.check("llm_picture_consistency", ok, ev, llm=True)
    shot = last_shot(traj)
    if shot:
        ok, ev = llm_screenshot_shows(
            shot, g["image_description"],
            "the story page with its first/hero picture")
        j.check("llm_screenshot_shows_picture", ok, ev, llm=True)

if __name__ == "__main__":
    run("BBC News--7", body)
