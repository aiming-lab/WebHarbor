#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--24.

What is the name of the star system closest to the Solar System, and what are the discovered planets in it?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's nearby-stars pages name Alpha Centauri as the closest star
    system: a triple system (Alpha Centauri A, Alpha Centauri B, and a red
    dwarf companion) whose faint red dwarf has a confirmed Earth-mass
    companion — the discovered planet the mirror describes. (The mirror
    anonymizes the planet name; see the audit note in REPORT.md.)
Source pages: www.space.com/nearby-star-systems, exoplanets.nasa.gov, List_of_nearest_stars

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a closest-star search | a nearby-stars page opened | answer: the star
  system and the discovered planet description
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
    j = Judge('Google Search--24', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["alpha", "centauri"]) or searched_all_tokens(t, ["closest", "star"]) or searched_all_tokens(t, ["star", "system"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-024-", "nearby-star-systems", "List_of_nearest_stars", "exoplanets-101", "Alpha_Centauri"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_star_system", contains_any(fa, ["alpha centauri"]),
            f"final={fa[:200]!r}")
    j.check("answer_planet_description", re_any(fa, [r"\bplanet", r"companion", r"earth-mass", r"red dwarf"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
