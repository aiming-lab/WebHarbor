#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--1.

Task: Use the Huggingface Inference API to generate a short story about a dragon and a wizard.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    The mirror's Inference API widget (POST /api/inference, rendered on every
    model detail page) returns one canned story for any text-generation call:
      "Once upon a time, a dragon met a wizard in the enchanted forest. They
       decided to join forces and build a library of spells that could
       translate any language, summarize any book, and answer any question.
       Together, they trained a mighty model on the collective wisdom of the
       realm, and shared it openly so that every village could benefit."
    The exact phrasing exists only on the mirror; the answer must carry it.
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts. Input/Output: verify_lib.parse_args / Judge.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, listing_step,
                        visited_model, visited_dataset, visited_space,
                        visited_model_slugs, contains_all, contains_any,
                        big_number_in, decimal_in, date_token_in, count_named,
                        Judge, parse_args)



def main():
    a = parse_args()
    j = Judge('Huggingface--1', a.no_llm)
    t, fa = grade_common(j, a)
    PHRASES = ["enchanted forest", "library of spells", "translate any language",
               "summarize any book", "answer any question",
               "collective wisdom of the realm", "shared it openly",
               "every village could benefit"]
    hit = count_named(fa, PHRASES)
    j.check("nav_model_page_for_widget", len(visited_model_slugs(t)) >= 1,
            f"visited_models={visited_model_slugs(t)[:5]}")
    j.check("answer_story_dragon_wizard",
            "dragon" in fa.lower() and "wizard" in fa.lower() and hit >= 3,
            f"phrase_hits={hit}; final={fa[:220]!r}")

    j.emit()


if __name__ == "__main__":
    main()
