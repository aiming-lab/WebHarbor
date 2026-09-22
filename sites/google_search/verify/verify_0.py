#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--0.

Find the initial release date for Guardians of the Galaxy Vol. 3 the movie.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Guardians of the Galaxy Vol. 3 was released in the United States on
    May 5, 2023. Every Vol. 3 detail page on the mirror (TMDb, IMDb tt6791350,
    Rotten Tomatoes, Marvel, Metacritic, Letterboxd, Fandango, Box Office Mojo,
    Wikipedia) shows May 5, 2023 as the US release; the Wikipedia infobox also
    lists the earlier Hollywood premiere (April 27, 2023), which is not the
    initial wide release. The Vol. 2 / 2014 distractor pages show other dates.
Source pages: the Vol. 3 result pages reached from /search?q=<task query> (SERP snippets and
    the knowledge panel do not carry the date)

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a search for the movie | a Vol. 3 detail page opened (not a Vol. 2/2014
  distractor) | answer: the initial release date
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
    j = Judge('Google Search--0', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["guardians", "galaxy"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-000-", "guardians-of-the-galaxy-vol-3", "guardians_of_the_galaxy_vol_3", "guardians_of_the_galaxy_vol._3", "tt6791350"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_initial_release_date", date_in(fa, "May 5, 2023"),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
