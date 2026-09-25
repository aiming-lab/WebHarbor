#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--5.

Article 'What is climate change? A really simple guide': what human
activities are causing climate change.

Checks: opened the explainer article; the answer states the burning of
fossil fuels plus at least two more on-page causes (deforestation,
intensive farming, industrial processes, transport) and the greenhouse
gas mechanism.

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

CONTEXT_PAGES = ["/news/earth"]
CONTEXT_SEARCHES = ["climate change", "really simple guide"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
CAUSE_FOSSIL = ["fossil fuel", "coal", "oil and gas", "burning fossil"]
CAUSE_OTHER = [["deforestation"], ["intensive farming", "farming", "agriculture",
                                    "cattle", "rice paddies"],
               ["industrial process", "industrial"], ["transport"]]
CAUSE_GAS = ["greenhouse gas", "co2", "carbon dioxide", "methane",
             "nitrous oxide"]


def body(j, traj, ans):
    opened = opened_article(traj, ["what-is-climate-change-a-really-simple-guide"])
    j.check("grounded_on_site", bool(opened) or _context_ok(traj),
            f"opened={opened}; context pages={CONTEXT_PAGES} "
            f"searches={CONTEXT_SEARCHES}")
    j.check("answer_states_fossil_fuels", mentions_group(ans, CAUSE_FOSSIL),
            "burning fossil fuels (coal, oil and gas) is the lead on-page cause")
    others = group_hits(ans, CAUSE_OTHER)
    j.check("answer_states_more_causes", others >= 2,
            f"additional causes hit={others}/4 (deforestation, farming, "
            f"industrial processes, transport)")
    j.check("answer_states_greenhouse_mechanism", mentions_group(ans, CAUSE_GAS),
            "greenhouse gases trap heat in the atmosphere")

if __name__ == "__main__":
    run("BBC News--5", body)
