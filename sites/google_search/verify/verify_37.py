#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--37.

Find the current top 3 super-earth planets and give a brief introduction to them.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    AUDIT NOTE (see REPORT.md): no mirror page names specific super-Earth
    planets; the NASA page describes the class (1-10 Earth masses, transit /
    radial-velocity discovery, habitability factors) generically. The widely
    documented top super-Earths (the seed's intended anchors) are
    Kepler-452b, LHS 1140 b and TOI-715 b. Grading anchors on the answer
    naming at least two real exoplanet designations with a habitable-zone /
    super-Earth introduction.
Source pages: exoplanets.nasa.gov super-Earth pages on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a super-Earth search | a super-Earth page opened | answer: at least
  two exoplanet designations with a brief introduction
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--37', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["super", "earth"]) or searched_all_tokens(t, ["super-earth"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-037-", "super-earth", "exoplanet-catalog", "types-of-planets", "top-3-earth-size-exoplanets"]),
            "an answer-bearing mirror page was opened")
    designations = r"\b(kepler[-\s]?\d+[a-z]|k2[-\s]?\d+[a-z]|toi[-\s]?\d+\s?[b-g]|lhs\s?\d+\s?[bc]|gj\s?\d+\s?[a-z]|gliese\s?\d+\s?[a-z]|hd\s?\d+\s?[bc])\b"
    import re as _re
    n_designations = len(set(m.group(0).casefold() for m in _re.finditer(designations, fa or "", _re.IGNORECASE)))
    j.check("answer_exoplanet_designations", n_designations >= 2,
            f"final={fa[:200]!r}")
    j.check("answer_super_earth_intro", contains_any(fa, ["habitable", "super-earth", "super earth"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
