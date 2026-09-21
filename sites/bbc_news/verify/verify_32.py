#!/usr/bin/env python3
"""Deterministic verifier for BBC News task BBC News--32.

The artificial intelligence section: its top headline and the companies
involved.

The AI section (/news/ai) lead is 'Artificial Intelligence: EU AI Act —
the rules coming into force in 2026' (15 Apr 2026); the companies the
story names are the GPT family (OpenAI), Anthropic's Claude, Google's
Gemini and Meta's Llama. Checks: opened the AI section (or an AI search)
and that article; the answer names the EU AI Act headline and at least
two of the companies.

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

CONTEXT_PAGES = ["/news/ai", "/news/technology"]
CONTEXT_SEARCHES = ["artificial intelligence", "ai act"]


def _context_ok(traj):
    return any(opened_page(traj, p) for p in CONTEXT_PAGES) or \
        any(searched(traj, t) for t in CONTEXT_SEARCHES)
COMPANIES = [["openai", "gpt"], ["anthropic", "claude"],
             ["google", "gemini"], ["meta", "llama"]]


def body(j, traj, ans):
    opened = opened_article(traj, ["artificial-intelligence-eu-ai-act-the-rules-coming"])
    context = (opened_page(traj, "/news/ai")
               or any(searched(traj, t) for t in ["artificial intelligence", "ai act"])
               or opened_page(traj, "/news/technology"))
    j.check("grounded_on_site", bool(opened) or context,
            f"opened={opened}; the top headline comes from the AI section or "
            f"an AI search")
    j.check("answer_names_top_headline",
            mentions_group(ans, ["eu ai act", "ai act"]) and mentions_number(ans, 2026),
            "top headline: EU AI Act — the rules coming into force in 2026")
    j.check("answer_names_companies", group_hits(ans, COMPANIES) >= 2,
            "companies: the GPT family/OpenAI, Anthropic/Claude, Google/Gemini, "
            "Meta/Llama (need 2)")

if __name__ == "__main__":
    run("BBC News--32", body)
