#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--8.

thesaurus happy; count synonyms and antonyms.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /thesaurus/happy | answer contains '8 synonyms' AND '8 antonyms' (deterministic) | screenshot shows lists
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, last_shot, shot_after_url,
                        contains_all, contains_any, answer_equals, extract_years,
                        extract_score, resolve_db, saved_words_for, user_exists,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Merriam-Webster--8', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_thesaurus_happy", navigated_to(t, "/thesaurus/happy"),
            f"navigated={navigated_to(t, '/thesaurus/happy')}")
    # counts: the page lists 8 synonyms and 8 antonyms. Agents phrase this many ways
    # ("8 synonyms" / "Synonyms: 8" / "8 (…)"). Require both keywords present AND the
    # count 8 appears at least twice (one per list), rather than a fixed phrase.
    fa_low = fa.casefold()
    j.check("answer_counts", "synonym" in fa_low and "antonym" in fa_low and fa_low.count("8") >= 2,
            f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "synonyms", "how many synonyms and antonyms of happy are listed")
        j.check("screenshot_shows_lists", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
